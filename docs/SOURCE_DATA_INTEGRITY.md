# Source Data Integrity

External source data is evidence, not an instruction to overwrite a company
record. Import code must preserve the last known good value whenever the source
response is unavailable, malformed, ambiguous, or cannot be linked through a
stable identifier.

## Financial Administration (FS)

Automatic FS updates require an exact IČO match. Items without an IČO are
reported as `unverified` and are not written to a company record. Name, address,
postcode, and fuzzy similarity are not sufficient for unattended bulk updates.

This intentionally favors incomplete data over a false association. A future
manual-review workflow may present unverified source items with evidence and a
human-approved target, but it must not reuse automatic fuzzy matching.

## Insurance debts

Insurance scraper outcomes are classified as:

- `found` — an identified company result with a valid amount;
- `not_found` — an explicit source message that no record exists; and
- `unknown` — transport failure, malformed response, or unrecognized page.

Only `found` and `not_found` may update the stored debt amount. `unknown`
preserves the last known value and records the error in `CompanySyncStatus`; it
does not advance the aggregate insurance-check timestamp.

Because of that last rule, an unrecognised *absence* is not a harmless gap: a
company whose "no record" answer is misread as `unknown` can never be marked
checked, so it stays due forever and is re-queued on every cycle. Each scraper
must therefore recognise its source's own no-record wording, and fail closed
only on genuinely ambiguous pages.

### What each source's response actually looks like

`vszp_debt.check_vszp_debt_get` is written against the real markup, which is
worth stating because it is not what one would guess:

- The result table's first cell is the name followed by a `<br/>` and
  `IČO: <number>`. Rows are matched by parsing that identifier and comparing it
  numerically — a substring test would let IČO `3413608` match the row for
  `34136088`, and the two may differ only in zero padding.
- The claim column (`cells[4]`) is a **bare number** (`6 641,86`); the page
  contains no `€` anywhere. The shared `is_money()` in `registers/utils.py`
  requires a currency symbol, so it cannot gate this column, and loosening it
  would weaken the guard the Socialná poisťovňa scraper relies on. VSZP's format
  is therefore validated locally (`_VSZP_AMOUNT_RE`) before the shared
  `parse_money()` converts it. Anything that does not match is `unknown`, never
  a zero.
- The absence of a company is stated explicitly — **"Nenašli sa žiadne
  záznamy."** Only that message is authoritative. An empty table *without* it is
  ambiguous and stays `unknown`, because it can equally be a server-side error.

`soc_poist_debt.check_socpoist_debt` follows the same principle, and its markup
is worth stating because the obvious reading of the page is wrong:

- Every search result — including "nothing matched" — is rendered by one Drupal
  view, `<div class="view view-debitors view-id-debitors …">`. **That container
  is the anchor:** its presence is what proves the site processed the query. An
  error, a captcha or an interstitial does not carry it, and the page is then
  `unknown` rather than a zero.
- A company that owes money gets a result count — `Dlžníci podľa zadaných
  kritérií: <strong>1</strong>` — followed by a table. A company that owes
  nothing gets the same view with **no count line at all**. The site publishes
  no "no records" sentence anywhere, so searching for one (as this scraper did
  until 2026-09-10, matching "nevyhovuje žiaden záznam") finds nothing on either
  page and every non-debtor reads as `unknown`.
- The amount is read from the row whose own IČO cell matches, and only when that
  row carries exactly one readable figure. Taking the first `€` on the page —
  the previous behaviour — can attribute another company's debt, or a number
  from the page furniture, to the company being checked.

### A parser can lose one branch and still look alive

Both failures above were *branch* failures, not outages. The VSZP scraper had
lost both of its answers; the Socialná poisťovňa scraper had lost only the
no-record one. The second is far harder to notice, because the source keeps
returning results: a success count, a success rate and a queue depth all look
healthy while it happens.

The damage is in the aggregate rule. `registers.tasks.update_insurance_debt`
advances `last_insurance_debt` only when **both** sources are authoritative, and
`schedule_insurance_debt_checks` re-selects every company whose timestamp is
still NULL. A source that can never say "no record" therefore keeps the majority
of 441 714 companies due for ever, and the `insurance` queue refills itself
indefinitely while draining at exactly its configured rate.

That is why `make ops-check` judges a source on **both** of its answers rather
than only on whether it succeeds at all — see `docs/DATA_PROTECTION.md`.

### Throughput

The insurance refresh is capacity-bound, not interval-bound.
`schedule-insurance-debt-checks-every-12-hours` only decides which companies are
*due* (`last_insurance_debt` older than 12 h, or never checked); it does not make
them complete in 12 h. With 441 714 companies, two sources per company, and the
deliberate `rate_limit='20/m'` on `registers.tasks.update_insurance_debt`, one
full pass takes roughly **15 days**. The rate limit exists to avoid an IP ban
from the state registries and is not a knob to raise casually — shortening the
cycle means raising load on a third party, which is a decision, not a tweak.
`make ops-check` reports queue depth and per-source success; `docs/ARCHITECTURE.md`
summarises the schedule.

## Focus Mode

Focus Mode pauses only future periodic scheduling outside its allowlist. It
never revokes active work or purges broker queues: queued source imports remain
durable work and may not be discarded merely to reprioritize the workers.

## RUZ run exclusivity

All supported RUZ full and incremental triggers create or reuse one active
`SyncJob` with the `ruz:global` concurrency key. The database enforces this
invariant while a job is queued or running, so worker-concurrency settings are
only defense in depth. The worker atomically claims that job before invoking
the RUZ command; a duplicated Celery delivery therefore exits without running
a second company-data import.

RUZ jobs must not be force-cancelled or redispatched by the admin API. Those
actions can interrupt an import after part of its data has been persisted.

### An unreachable registry must not read as an empty one

The RUZ import loop ends on `if not id_data or not id_data.get('id')`, logging
`No more company IDs to fetch.`.

Every `get_*` method in `backend/registers/integrations/ruz_api.py` catches
`requests.exceptions.RequestException` and returns `None`, which at that point
was indistinguishable from a genuine "nothing further". A network failure
therefore ended the loop, and the code below it ran `progress.complete()` and
`complete_job(job)` — marking the whole sync `completed` on a truncated run.

This was first recorded here as **latent, not demonstrated**, on the strength of
the fail-open line occurring **0 times** in the retained worker logs while the
legitimate `Reached the end of the list.` occurred once. That window was about a
day long, so it was evidence about the window and not about the path.

**On 2026-09-11 it fired twice.** The 00:22 and 06:22 beat runs — jobs #13 and
#14 — both failed to resolve `www.registeruz.sk`, exhausted their retries,
printed `No more company IDs to fetch.`, and were stored as `completed` with
`processed_items=0` and a final `Errors: 0`. Both requested the *same* page
(`pokracovat-za-id=2624307`, the stored cursor, in the failing URL of both), so
the cursor did not move and no company was fetched at all.

**No control catches it.** `sync_health` prints a run's counters and explicitly
declines to judge them — "how many items a job should process depends on the
run, so no threshold would be honest" — and the beat-scheduled-run control
judges a job type whose newest attempt ended `failed`, while these ended
`completed`. A transport failure that ends a run therefore passes every control
that reads sync jobs, and the row it leaves is indistinguishable from a run that
found nothing new.

**Fixed 2026-09-11.** `get_changed_company_ids` now lets the
`RequestException` propagate instead of answering `None`, so the loop's
`except Exception` runs `progress.fail()` and `_run_ruz_command` runs
`fail_job()` — the run is stored `failed`, with the transport error as its
`last_error`, and the Celery task fails audibly.

The fix belongs in the client rather than in the loop, because the ambiguity is
in the *value*: a caller cannot tell `None`-means-nothing from
`None`-means-unreachable, and no amount of care at the call site can recover
what the value no longer carries. The other `get_*` methods keep swallowing, and
can: a company that cannot be read is counted as a failed item and stays
visible, so their `None` is not read as a statement about the whole run.

The two halves of the rule are pinned by `RuzTransportFailureTests` — a
transport failure on the *first* call fails the run, and a page that genuinely
carries no IDs still ends it `completed`. The second test is not decoration: a
run that finds nothing new is the normal case (five beat runs a day look like
this), so a fix that made empty pages fail would trade a silent failure for a
constant alarm.

Both repair commands call the same client and were reading the same ambiguous
`None`; their loop now fails and records `progress.status='failed'` rather than
printing `Koniec zoznamu` over a page it never received.

### The incremental cursor only ever moves forward

`fetch_ruz_data.py:253` sets `pokracovat_za_id = company_ids[-1]` after each
page and reads it back from `progress.last_processed_ruz_id`, so the cursor only
ever moves **forward**; `zmenene_od` is read from the stored
`progress.zmenene_od` (`fetch_ruz_data.py:157`), which is frozen at
**2026-08-04** and never advanced.

A live API probe on 2026-09-10 measured what the cursor actually does, and it is
not a filter over the changed set:

| Request | IDs returned |
|---|---|
| `zmenene-od=2026-08-04` alone | `66, 133, 280, 369, 496, …` — **scattered**: the changed entities |
| the same, plus `pokracovat-za-id=2617790` | `2617791, 2617792, 2617793, …` — **consecutive**, 1000 per page, `existujeDalsieId: true` |

So `pokracovat-za-id` does not paginate the changed set — it switches
`/api/uctovne-jednotky` to listing entities in ID order, and **the change-date
window stops applying at all**. Every real run passes the stored cursor
(`fetch_ruz_data.py:208`), so `zmenene_od` is inert for every run after the
first and this sync only ever advances into newly-added tail IDs. A change to an
*existing* company is therefore never fetched again, however it changes.

Measured the same day: the ID space ends below 2,700,000, so the walk is bounded
and a run that finds nothing new exits in milliseconds. That is what the
six-hourly beat normally does, and it is why five runs a day can "succeed"
having processed nothing at all.

**But the tail is not a steady stream — it arrives in batches, so a run is either
instantaneous or a real import.** Measured on 2026-09-10: the 12:22 beat run
reached the end of the list in **4 s** with the cursor at 2,617,490, on a valid
empty page. The next run, dispatched by hand at 18:27 after a worker fix, walked
**6 817** IDs from that same cursor to 2,624,307 and processed 6 850 records over
**25 minutes**. Re-probed at 19:05, nothing exists above 2,624,307 and the run's
own end-of-list line said `Errors: 0`. So those 6 850 records were **not** a
backlog the beat had been failing to collect — they are entities RUZ gave IDs to
between 12:22 and 18:27. The cursor was never behind; the registry's tail simply
moved, and it moved by thousands at once.

Known limitation, undecided. Fixing it means first choosing how changes are to
be found at all — dropping the cursor to use the date window would ask the API
for the registry's entire changed subset, from ID 66 upward — so it is a load
decision, not a bug fix.

## Which RUZ writers announce a dissolution

`Company.datum_zrusenia` is written by five upsert sites, all shaped
`Company.objects.update_or_create(ico=..., defaults=...)`. `update_or_create`
discards the row it matched, so after the write there is no way to tell whether
the company was *already* dissolved — the transition `NULL -> date` has to be
captured by reading the previous value **before** the write.

Two writers do that and notify watchers through
`notifications.services.detect_status_change`:

| Writer | Reached by |
|---|---|
| `fetch_ruz_data.py` → `update_or_create_company` | the 6-hourly beat, and any manual `make fetch-ruz` |
| `registers/tasks.py` → `_update_company_from_ruz_data` | on-demand sync, search-and-add, `orchestrate_full_company_sync` |

**The three `repair_ruz_*` commands deliberately do not.** They are manual
repair tools that already require a backup to be taken first, and their job is
to correct a known-wrong table, not to report registry news. Leaving them
unwired means a *missed* notification during a repair run — not a wrong one,
which is the right trade for a corrective tool.

Only the direction `NULL -> date` is announced. A date that moved or was
cleared is a correction, and alarming on RUZ's own fixes would make the
notification worthless. The same guard is what makes a writer safe to repeat:
after the first write the stored value is a date, so the next sync of that
company finds nothing to announce. No dedupe table is involved.

Not covered by design: the two staff write paths (`AdminCompanyViewSet` and the
Django admin form) can also overwrite `datum_zrusenia`. A manual edit by staff
is a deliberate act, not a registry event, so it does not notify.

## A date we cannot read must not erase a date we hold

`parse_date` collapses two different things into `None`: a field RUZ **omitted**,
and a field it sent in a shape we cannot parse. Both writers stored that `None`
alike, which is how an upstream format change becomes data loss.

Measured against the live API on 2026-09-10, before changing anything:

| Payload | `datumZrusenia` |
|---|---|
| 20 dissolved companies | present, ISO, parses, matches the stored value |
| 8 active companies | absent |

So absence is a *statement* — "this company is not dissolved" — and it is the
only way RUZ revokes a dissolution. An unreadable value is *noise*, and is never
an instruction. `registers.integrations.ruz_api.apply_ruz_dates` maps all three
RUZ date fields on that distinction: absence still clears a stored date, and an
unreadable value is left out of the `defaults` dict entirely so
`update_or_create` keeps what is stored, with an `ERROR` naming the IČO, the
field and the raw value.

The failure this removes, in order: RUZ changes its date format → every
dissolution date is silently erased → 120 289 companies read as active → the
format is fixed → every one of them "newly dissolves" and notifies.

**This is a judgement, not a settled fact.** The asymmetry is deliberate —
an unreadable value costs a stale date, which is visible, where writing it
through costs 120 289 dates, which is not. It is one-sided on purpose: if RUZ
ever *does* mean "clear this date" by sending something unreadable, we keep a
stale date and say so rather than clearing. The measurement above is one day
old and the format has never changed, so nothing here has been tested by
reality.

**A refusal that only reaches a log line is not a control.** The guard refuses
the write, and `registers.services.sync_engine.record_ruz_date_outcome` records
that refusal against the source as a `CompanySyncStatus` row
(`source='ruz'`, `error_type='parse_error'`). That is what puts it inside
`make ops-check`'s reach:

| Companies refusing in the window | `source_health` verdict |
|---|---|
| 0 | **OK** — a reading, not a lack of evidence |
| 1 to 199 | counted and shown, **not judged** |
| 200 or more | **FAIL**, and `make ops-check` goes red |

The threshold is inherited, not tuned for RUZ, and it keeps its meaning: a lone
malformed record is an upstream typo and must not hold the gate red forever, or
the alarm stops being read. The cost is that a *slow* trickle takes longer than
a day to reach 200 refusals — which is why the `ERROR` log and the count in the
gate table both exist alongside the verdict.

**`ruz` writes an attempt row like every other source, and that is the fix.**
It used to write a row *only* when it refused a date and never a success —
which made the refusal invisible to every reader that judges on
`consecutive_failures`, and made the source read "0 % coverage" on the admin
dashboard while it was the healthiest one there. `record_ruz_date_outcome` now
writes one row per company per run, success or refusal, through the same
`update_company_status` every other source uses, and both RUZ writers call it —
so the six-hourly command and an on-demand sync cannot drift apart.

The bypass had a real reason and the reason is gone. With no success path, a
written failure could never be cleared: `consecutive_failures` would climb on
every re-fetch of the same company with `next_retry_at` backing off towards its
24 h cap, arming a trap for whichever reader trusted it next. A success row is
what makes writing the failure honest.

Cost, measured rather than assumed: one extra upsert per company per run. The
six-hourly incremental run processed 6 850 records in 26 minutes on 2026-09-10,
so the marginal cost is a few queries per second; a full resync pays it on
441 714 companies, in a run that is already manual, backup-gated and takes
hours. A refusal does **not** double-count: the refused fields of one record go
in as one attempt, so two unreadable dates are `consecutive_failures = 1`.

**The refusal keeps its own line in the gate, because the attempts table cannot
see it.** A partial format change does not silence a source — most records
still parse, `succeeded` never reaches 0, and the attempts line reads OK. Only
the refusal count distinguishes it, so `ruz` now appears in *both* tables: the
attempts row is the denominator, and the refusal row is the diagnosis.

```
  source          attempts  succeeded    found  no-record  (24h window)
  ruz                 6850       6847        -          -  OK
  ruz                  200 companies refusing a date field  FAIL
  (source 'ruz': 200 companies have a date field that cannot be read -- the
   source's shape has changed. The affected values were kept, not overwritten,
   so the stored data is stale rather than gone. A company leaves this count as
   soon as a sync reads its dates cleanly again.)
```

A source that fails both lines is **one** unmet control, not two: when every
attempt refuses, the two readings describe one event, and counting it twice
would make the gate's own headline number wrong.

**The refusal is a state, not a scar.** The count is read from
`consecutive_failures`, which the row carries for its *latest* attempt — so a
company whose next sync reads its dates cleanly drops out. Had the gate instead
counted rows that had ever refused, a fixed upstream typo would hold
`make ops-check` red forever, which is how an alarm stops being read.

**What the admin surfaces now see.** All four read `consecutive_failures` and
nothing else, so one write path fixes them without touching any of them:

| Reader | Keys on | Sees a refused date? |
|---|---|---|
| `adminapi/views/dashboard.py:39` `company_failures_24h` | `consecutive_failures__gt=0` | **yes** |
| `adminapi/views/dashboard.py:97-104` per-source card | `last_succeeded_at__isnull=False`, `consecutive_failures__gt=0` | **yes** |
| `adminapi/services/company_filters.py:265,426` `sync_state=failing` | `consecutive_failures__gt=0` | **yes** |
| `lead_scoring/services/scoring.py:178-180` | `Avg(consecutive_failures)` | **yes** |

So the gate tells you **how many** records carry an unreadable date and the
company screens now let you find **which** ones.
`adminapi/tests/test_dashboard_refusals.py` asserts this through the real HTTP
endpoints rather than the ORM, because the claim is about what the screens
report.

One gap, deliberately recorded rather than hidden: `CompanySyncStatus` keys to
`Company`, and RUZ also writes SZCO records to `IndividualEntity`. A refused
date on an individual cannot be attached to a row, so it is **counted nowhere**
and the command now says so on stderr instead of dropping it in silence. The
gate therefore does not cover that third of the RUZ surface. Closing it means a
nullable FK or a second table plus a migration on a production volume, for a
signal that has not fired once in production — so it stays a named gap, not a
silent one.

**A caller must hand `detect_status_change` the value it wrote, not the row read
back.** `update_or_create` returns the row as it now stands, so where a writer
declines to write, `company.datum_zrusenia` is the *untouched stored* date —
and passing that as new, with `old=None` because the pre-read is skipped,
announces a dissolution that never happened. That is the guard manufacturing
the very alarm it exists to prevent; `RuzDateGuardTests` in
`registers/tests_sync_pipeline.py` pins it.

## Status vocabulary: the API produces two, the frontend declares four

`Company.datum_zrusenia` is the only status input, and the product derives
exactly two labels from it — `Aktívna` and `Vymazaná`. `frontend/types.ts`
declares four (`+ V likvidácii`, `V konkurze`) in three interfaces, and
`StatusBadge` renders all four, but nothing the backend emits can reach the
extra two: they survive only in `mockData.ts` and the `ENABLE_MOCK_DATA`
fixtures.

This is **aspirational, not wrong, and not to be "fixed" by narrowing the
type.** `notifications.models.NotificationPreference.on_status_change` carries
`help_text='Zrušenie, likvidácia, konkurz'`, so likvidácia and konkurz are
planned; the union is where they will land. No code branches on either label
today.

That `help_text` over-promises — only dissolution is wired, so a staff user
reading the admin checkbox is told about two things that cannot happen. The
user-facing copy in `NotificationPreferences.tsx` was corrected to say what the
feature does; the model string was left alone deliberately, because changing
`help_text` generates an `AlterField` migration, and a migration means taking a
verified backup first. It belongs with the next change that migrates anyway.

The two reachable labels, by contrast, are **duplicated, not shared**. The same
`'Vymazaná' if datum_zrusenia else 'Aktívna'` decision is written out in six
places — `connections/views.py:32,86,200`, `companies/serializers.py:36,232`,
`companies/services/pdf_report.py:328` — with a seventh spelling (unaccented
`Zrusena`/`Aktivna`) in `companies/admin.py:291`. `notifications.services`
defines its own pair rather than importing one. That is a real defect, and it is
a separate, larger change than the one above: unifying it means one vocabulary
module that the API, the PDF, the admin and the notifications all read from. It
has not been done.

## A filter over data we do not hold fails silently

The admin preset **IT firmy v Trnave bez dlhov** returned **0 rows**. The
operator's question was whether the preset was misconfigured. It was not: every
condition in it was applied exactly as written, and the honest answer was that
the population it describes is 136 companies and the filter asked for 7
conditions while its own description promised 5.

Measured on 2026-09-11, narrowing one condition at a time:

| Condition | Companies |
|---|---|
| active, Trnava, PSČ 917, no debts | 4 481 |
| + NACE 62 | **136** |
| + has an ORSR profile | 4 |
| + has an imported financial statement | **0** |

Two conditions (`has_financials`, `has_orsr`) had been added on top of the four
the description names. Neither was broken — both were simply true of almost
nobody. The preset was dropped from them rather than the description reworded,
because the description is what the operator reads, and those two conditions
described *the data we wish we had*, not the filter the preset claims to be.

**The general shape is the point.** A filter that requires a dataset we do not
hold does not error, does not warn and does not degrade — it returns an empty
table, and an empty table is indistinguishable from "we have no such data",
from "the filter is wrong", and from "the import is running fine but this
company genuinely has no statement". The preset was correct for months while
returning nothing, and the only reason it was found is that a human noticed an
empty screen and asked.

This is the same defect class as the rest of this document, one level up: the
import failure recorded in *An unreachable registry must not read as an empty
one* was itself invisible, and the preset was where it finally surfaced — as a
number that was wrong in a way nothing was measuring.

**Fixed 2026-09-11** in `backend/adminapi/services/company_filters.py`. The
population behind the preset (136) is the pilot sample for the financials-import
recovery, so the two findings are the same finding seen from two ends.

`CompanyPresetTests` in `backend/adminapi/tests/test_company_filters.py` pins
both halves: that no preset names a filter key `apply()` does not implement —
checked against the compiled query rather than a hand-kept list of key names, so
it holds on an empty table where every assertion about results would pass
vacuously — and that a company with no financial statement still matches the
preset. `profitable_it` deliberately keeps `has_financials`: its description
promises statements, and `profit_state=profit` requires one anyway.

## The financials rotation selected the same 500 companies 32 times

The preset above was the symptom. The cause was upstream, in
`schedule_ruz_financials_sync`.

Its selection was `Company.objects.order_by('id')[:limit]` — no cursor, no
`offset`, nothing that remembers where the last run stopped. Celery Beat called
it with `args=[500]` every 12 hours, so **every run chose the same 500
companies**. Measured on 2026-09-11, after 32 runs of the 12-hour beat:

| Measure | Value |
|---|---|
| Companies with any financial result | 309 |
| Rows in `CompanyFinancialResult` | 3 506 |
| Of those 309, sitting inside RUZ ids 202–701 | **297** |
| `CompanySyncStatus(source='financials')` rows | **0** |
| Eligible companies (ORSR forms, not dissolved) | 251 598 |
| Eligible companies never attempted | **251 598** |
| `PeriodicTask` #6 `total_run_count` | 32 |

Nothing failed. No error was logged, no alert fired, no job turned red — the
task ran, completed, and reported success 32 times. Coverage simply stopped at
0.1 % of the population and stayed there. It is the same defect class as the
rest of this document, in its purest form: **a scheduled job that looks alive
and never advances.**

### `rows=0` used to mean four different things

`RuzFinancialsSyncService.sync_company()` returned `0` when the registry was
unreachable, when the company had no RUZ record, when it had no statements, and
when the statements it had yielded nothing readable. Callers could not tell
these apart, so "we never reached the registry" was recorded, counted and
displayed exactly like "this company genuinely has no statements".

That is why the second half of the measurement above is 0. A company whose
financials attempt failed left **no row at all**, so there was no way to count
how many companies had been tried and how many had not — and the two are the
same number only if nothing ever fails.

**Fixed 2026-09-11.** `sync_company_detailed()` returns a
`FinancialsSyncResult` carrying a `FinancialsOutcome`:
`RECORDED`, `NO_STATEMENTS`, `NOT_IN_RUZ`, or `UNREACHABLE`. The first three
are *knowledge about the company*; the fourth is *ignorance about the
registry*. `sync_company()` is kept as a one-line delegate so existing callers
and tests keep their signature.

`RuzApi` gained `raise_on_transport_error` (default `False`, so all six
construction sites and every existing caller behave byte for byte as before).
The financials service builds its client with it on, so a transport failure
arrives as an exception rather than as `None`. A **404 stays `None` either
way** — the registry answered, and its answer was "no such record". A 5xx after
the retry session has given up is not an answer, and raises.

`sync_company_and_record()` is the single owner of the outcome → status rule.
An unreachable registry is recorded as a **failure** with
`consecutive_failures` and `next_retry_at`; the three answered outcomes are
recorded as **successes**. Recording "checked and empty" as a success is what
makes it countable — and it is why `CompanySyncStatus` now distinguishes the
two populations that used to share one silent state.

The transport failure deliberately does **not** propagate.
`orchestrate_full_company_sync` builds its `group(...)` with
`update_insurance_debt` as the chord callback, so an exception here would stop
that callback from ever running and a company would quietly stop having its
insurance debts refreshed — a second outage caused by the handling of the
first. Repetition is owned by `next_retry_at` alone, not by Celery autoretry.

### A success must schedule itself, or the fix reintroduces the bug

`update_company_status(success=True)` cleared `next_retry_at` to `NULL`, and
the due-query reads `NULL` as **due now**. So the first version of this fix
would have refilled every batch with the companies the previous batch had just
synced, and the never-attempted population would never have been reached —
the original bug, reintroduced by its own repair.

`update_company_status` therefore takes `retry_after`, and an answered outcome
passes `ANSWERED_RETRY_AFTER` (365 days). A failure ignores it: how long to
wait after a failure is `compute_next_retry`'s exponential backoff, not a fixed
delay. `SyncCompanyAndRecordTests` pins the distinction, and
`test_the_rotation_only_advances_because_attempts_are_recorded` states the
coupling out loud: the status row is not bookkeeping, it **is** the cursor.

### The batch: retries first, then new ground

`financials_sync_batch()` draws from two populations:

1. **Retries** — `financials` status rows whose `next_retry_at` has arrived,
   capped at `1/RETRY_SHARE` (a quarter) of the batch, so a failing minority
   cannot spend the whole batch on itself.
2. **New ground** — companies with no `financials` status row at all, ordered
   by `id`. An attempt always writes a row, so the head of this queue moves
   after every batch: resumable and deterministic without storing a cursor.

The task **name is unchanged** (`schedule_ruz_financials_sync`) and only its
internals changed. The admin-managed `PeriodicTask` row, `FOCUS_KEEP_TASKS`,
`CELERY_BEAT_SCHEDULE`, the manual dispatcher and two tests all key on that
name, so keeping it means no `PeriodicTask` row had to be edited, no migration
was needed, and a rollback is a code revert rather than a scheduler change.

`eligible_only` (ORSR-eligible legal forms, not dissolved — the same population
`schedule_missing_orsr_sync` uses) became the default. The beat passes only
`limit`, so this is what decides what the scheduled path imports; both manual
callers pass the flag explicitly and are unaffected.

### The pilot, measured 2026-09-11

The 136 companies behind the reported symptom (Trnava / PSČ 917 / active /
NACE 62 / no debt) were run through the fixed path. Every outcome was
recorded, and for the first time the four cases are countable separately:

| Outcome | Companies |
|---|---|
| `recorded` — statements imported | 114 |
| `no_statements` — registry answered, company has none | 22 |
| `not_in_ruz` | 0 |
| `unreachable` — registry could not be read | 0 |

1 262 rows written, **0 errors**. Coverage moved from 309 companies / 3 506
rows to **423 companies / 4 724 rows**, and
`CompanySyncStatus(source='financials')` from **0 rows to 136** — the trace
that did not exist before, and the reason the previous measurement could only
say "309 covered" and never "251 598 never attempted".

`profitable_it` moved 5 → 108: it keeps `has_financials`, and its description
promises statements, so the preset was right all along and simply had no data
to be right about. `clean_and_healthy` could not have moved: before the pilot
its `sync_state=healthy` had zero `financials` rows to judge, and 136 rows with
`consecutive_failures=0` cannot change an `Exists(failures > 0)` either way.

**A warning about how to check this.** Running the selection twice without
syncing in between returns *the same companies both times* — which is also
what the broken code did, so the naive check cannot tell the fix from the bug.
The rotation advances only because an attempt records a status row. The canary
therefore selects a batch, syncs it, and selects again:

| Run | Companies chosen |
|---|---|
| Selection before any sync (batch 1) | ids 202 – 284 |
| The old selection, after batch 1 was synced | ids 202 – 251 — **unchanged** |
| Selection after batch 1 was synced (batch 2) | ids 285 – 383 |

Intersection of batch 1 and batch 2: **empty**.

### Honest arithmetic, and what a rollback would not recover

500 companies per 12 hours is 1 000 a day, against 251 598 eligible companies:
about **252 days** for one pass. That is today's configured pace and this
change does not alter it — the point was to make the rotation advance at all,
and to make its pace measurable. Changing the pace is a separate decision.

`companies_due_for_sync()` — dead scaffolding with zero callers since it was
written — is now the retry half of the batch, ordered with an `id` tiebreak
because every row written by one batch shares a `last_attempted_at` to the
microsecond.

**Known limitation, not fixed here.** The same non-advancing selection exists
in `fetch_ruz_financials` batch mode and in the legacy dashboard's manual
trigger. Both are operator-bounded and print what they chose, so they fail
visibly rather than silently; they are recorded here rather than changed.
