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

**Nothing measures whether FS data is still fresh.** Stated plainly here
because the alternative is a reader assuming it is covered somewhere. FS is a
bulk ingest — `update_fs_data` downloads the national dataset, matches it by
IČO in one pass and `bulk_update`s the matches — so it never visits a company
and has no per-company attempt to record;
`CompanySyncStatus.SOURCE_CHOICES` declares `fs`, and **no runtime code writes
that value**. `migrate` seeds none either.

Per-company rows are deliberately *not* invented for it. Forty thousand rows a
day, rewritten, would be a precision that does not exist: the ingest either
read the file or it did not, and that fact belongs to the run, not to each
company. `source_health` therefore prints `fs` and verdicts it **`not
measured`** — never `OK`, because `OK` would claim a check this command cannot
make. See `SOURCES_WITHOUT_ATTEMPT_ROWS` in
`backend/registers/management/commands/source_health.py`.

The larger gap is one step further out: `update_fs_data_task` is **not** a
`BaseSyncTask`, so a run creates no `SyncJob` row either. Between the three —
no job, no item, no status — the daily ingest of the national dataset has **no
control anywhere that would notice it had stopped**. The data would simply age.
A single `SyncJob` row per run (not per company) is the cheap honest fix; it is
recorded here as new work with a clear brief rather than done as a side effect
of something else.

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
of 441 714 companies due for ever — a due population that never shrinks, however
fast the queue behind it drains.

That is why `make ops-check` judges a source on **both** of its answers rather
than only on whether it succeeds at all — see `docs/DATA_PROTECTION.md`.

Measured on 2026-09-12, after that scraper defect was fixed, the aggregate rule
was **no longer the binding cause**: of the 25 398 companies whose timestamp was
stale, **0** carried a failed VŠZP attempt. The queue was still growing, for the
reason in the next section.

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

**The enqueue side is bounded, and that is new.** Until 2026-09-12 the scheduler
enqueued the *entire* due population every tick — 439 817 companies, measured
that day — which no drain rate can absorb. The queue reached **5 108 434 pending
messages, ~5 GB of Redis**, the largest single consumer in the stack, and the
growth was unbounded rather than merely slow. Three things followed from it, and
only the first is the one a queue-depth metric shows:

- The backlog itself, re-created at every tick.
- The worker only ever reached the *oldest* messages. Measured: its last
  recorded attempt was 14:15 while it kept running past 15:20.
- **The scheduler ran on the queue it floods.** Beat dispatched it at 07:50 and
  a worker first ran it after 11:00; it then executed at 03:11, 04:17, 11:14,
  11:49, 12:04, 13:55, 14:15, 14:19, 14:34, 14:39 and 14:53 — roughly **8.4
  million messages enqueued in one day against 14 400 drained**. Each run builds
  ~440 000 `delay()` calls, so with `--concurrency=2` the worker spent its time
  scheduling instead of checking.

Three changes, all in `registers/tasks.py` and `backend/settings.py`:

1. The batch is capped at `INSURANCE_BATCH_PER_TICK`, derived from the rate limit
   so the two cannot drift, and carried as `args: [14400]` on the beat entry so
   it can be retuned without a deploy — the shape `schedule_ruz_financials_sync`
   already had.
2. The batch is ordered `nulls_first`. Postgres sorts NULLs *last* under a plain
   ascending order, so without it the 25 398 stale companies would have been
   re-chosen every tick while the 414 419 never-checked ones waited for ever.
3. The scheduler runs on `celery`, not on the queue it fills.

Where the routing actually lives is the trap worth recording: the admin-managed
`PeriodicTask` row carries `queue` explicitly and `DatabaseScheduler` runs **the
row**, so `CELERY_TASK_ROUTES` and `CELERY_BEAT_SCHEDULE.options.queue` are both
inert for a task whose row exists. All three now agree; changing the settings
dict alone would change nothing on a live system.

The rate limit is unchanged, so one full pass is still ~15 days. What changed is
that the queue is now bounded by that figure instead of ignoring it.

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

**A partly readable company now says so.** Inside `RECORDED`, a company whose
thirteen statements all parsed and a company whose twelve of thirteen parsed
were the same value: `rows > 0`. Only the second is the early warning that the
first is about to stop being true, so the result carries `N of M statement(s)
readable` in its `detail` whenever any statement was skipped. The count is on
the result rather than in a log line because the trend is what matters and a
log line cannot be counted.

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

## One filter, two answers, and the wrong one on screen

`sync_state=healthy` had two branches, and they disagreed about the largest
population in the table.

`_apply_sync_state` reads the annotation `sync_failures` when the queryset
carries it — the admin listing does, every other caller does not. The annotated
branch was:

```python
return queryset.filter(sync_failures=0)
```

`sync_failures` is a `Subquery`, so a company with no `CompanySyncStatus` rows
at all gets **NULL**, not 0 — and `NULL = 0` is NULL, which Django reads as
false. Every company that had never been synced by a source that writes status
was therefore silently dropped. Measured 2026-09-11 on the same filter through
the two paths:

| Path | `clean_and_healthy` |
|---|---|
| Unannotated (every other caller) | 275 912 |
| Annotated (the admin listing, what the operator sees) | 11 451 |

A difference of **264 461 companies**, all of it companies whose only sin was
never having failed anything.

**The replacement took two attempts, and both wrong ones were plausible.**

```python
queryset.exclude(sync_failures__gt=0)   # still 11 451
```

`NOT (NULL > 0)` is NULL too, so `exclude()` drops the row as well — the fix
that reads as the obvious inversion of the bug reproduces it exactly. The only
form that works names the NULL:

```python
Q(sync_failures=0) | Q(sync_failures__isnull=True)
```

which is also what the `failing` branch beneath it has always assumed, since
`sync_failures__gt=0` treats NULL as "not failing". **Absence of a failure is
not a failure**, and the two branches now have to agree about that.

`_condition_to_q` — the filter-builder path — carried its own copy of the same
expression and got the same fix. `SyncStateBranchTests` runs both branches
against both values and asserts they return the same set, and it is a test
rather than a comment because the fix is one `isnull` away from being undone by
anyone who reads `filter(sync_failures=0)` as the natural spelling of "has no
failures".

**What this changes for the operator.** The preset `clean_and_healthy` goes
from 11 451 to **275 912** companies. The number is not new data — it is the
same table, asked a question that now has one answer instead of two — but the
preset's *meaning* moves with it: it now includes 264 461 companies that have
never been checked by any source that writes status. Read plainly, "clean and
healthy" now means **"no known failure"**, not "verified clean". That is the
honest reading given the old behaviour recorded "never looked at" as unhealthy,
but the name promises more than the data can. A third value — the one this
vocabulary lacks — is *unknown*; `sync_state` offers only `healthy` / `failing`
/ `blocked`, so a company nobody has ever tried cannot say so. `blocked` is
unaffected: it reads an `Exists` annotation, which is boolean and never NULL.

## An empty result must say which condition emptied it

The preset above returned 0 rows for months and no screen could say why. The
report endpoint now answers that question itself, and only when it is asked by
an empty result.

When `count` is 0, `_zero_diagnosis()` drops one filter condition at a time and
counts what remains, ordering the conditions by how many companies their
removal restores. The conditions come from `_effective_filter_params()`, which
is also what the report itself was built from — the preset's conditions are
merged into the request's there and nowhere else, so a diagnosis that read
`request.query_params` directly would have diagnosed a filter nobody ran.

The counts are taken over a bare `Company` queryset rather than
`_listing_queryset()`: the listing carries a dozen subquery annotations for its
table columns, and paying for them once per condition would make an empty
result the slowest request in the admin. That the filter service answers
identically on both querysets is exactly what `SyncStateBranchTests` pins — the
two fixes share one invariant.

The builder then shows it (`frontend/admin/pages/CompaniesBuilderPage.tsx`):
each condition by its label, its value, and how many companies would remain
without it — plus the reading that matters, that a small number means *data we
do not hold yet*, not *a broken filter*. That distinction is the whole finding:
an empty table is what this defect class looks like from the outside.

**Not covered.** The diagnosis only relaxes one condition at a time. A result
emptied solely by the *combination* of two conditions restores nothing when
either is dropped alone, so neither is named and the panel stays silent — the
same empty screen this section is about. Pairs would cost a quadratic number of
counts on the slowest path in the admin, so the limitation is recorded rather
than paid for.

## A control that omits a source is not a control

`source_health` used to build its table from
`CompanySyncStatus.objects.values("source")` — the rows that exist — so a source
with **no** rows produced no line at all. Measured on the live stack
2026-09-11, `make ops-check` listed `financials`, `social` and `vszp` and said
nothing whatsoever about `ruz`, `orsr` or `fs`.

A missing line is not a neutral absence. It reads exactly like a source that was
checked and found healthy, which is the one thing it never means. Under that
silence two different things were invisible at once: `orsr` had a writer that
did not exist, and `ruz` had a task that had not yet run against the fix in
commit `8f40586`. Neither could be told from a healthy source, and neither could
be told from the other.

The table is now driven by the **declared vocabulary**
(`CompanySyncStatus.SOURCE_CHOICES`) rather than by what came back, so every
source gets a line, including the ones with nothing to report. What cannot be
measured is then *named* as unmeasured rather than left to be inferred:
`SOURCES_WITHOUT_ATTEMPT_ROWS` says of `fs` that it records no per-company
attempt and that nothing here measures its freshness.

**Silence is judged per source, because it does not mean the same thing
everywhere.** A source whose task draws from a due-list that cannot be empty
has no way to be idle by accident — attempting nothing there is a finding. A
source that records only what the registry reported as *changed* is merely
quiet. Two declarations carry that distinction:

| Declaration | Sources | Zero attempts in the window |
|---|---|---|
| *(none)* | `orsr`, `financials` | **FAIL** — their due-lists are never empty |
| `SOURCES_THAT_MAY_BE_SILENT` | `ruz` | OK, and the reason is printed |
| `SOURCES_PAUSED_BY_FOCUS_MODE` | `vszp`, `social` | OK *while Focus Mode is active* |
| `SOURCES_WITHOUT_ATTEMPT_ROWS` | `fs` | `not measured` |

`ruz` writes a row per company the registry reported as changed, so a 24-hour
window in which nothing changed produces zero rows on a run that worked
perfectly; failing it would be a false alarm. Focus Mode switches off
`vszp`/`social` periodic tasks **by design** — a uniform zero-attempt rule would
turn the gate red every time an operator used a documented feature, and an alarm
that cries wolf is one that stops being read. `orsr` and `financials` stay a
hard FAIL because `registers.services.focus_mode.FOCUS_KEEP_TASKS` guarantees
they always attempt.

This was a deliberate deviation from the plan approved for this increment, which
specified a uniform rule; the false alarms above are why it was not implemented
as specified, and the deviation is recorded in the commit that made it.

## ORSR had no writer at all

`CompanySyncStatus` held **zero** rows with `source='orsr'` and no code path
able to create one. ORSR wrote `OrsrCompanyProfile` and nothing else — the only
thing that had ever written an `orsr` status row was an unused
`tracked_sync_task` decorator, and a one-off backfill in migration
`0008_admin_overhaul`. Everything reading that table therefore covered a
population that silently excluded the source, and the previous section is what
made it visible rather than inferred.

It also had no **backoff**, and both ways an attempt can fail ended in a dead
end:

- `OrsrScraperError` is raised *after* `OrsrSyncService.sync_company` has
  written `fetch_ok=False` onto the profile. The company therefore leaves the
  `orsr_profile__isnull=True` population and `schedule_missing_orsr_sync` never
  selects it again.
- Any other exception — a transport failure inside `RpoClient` — writes nothing
  at all, so the company stays in that population and is re-dispatched at the
  head of an `order_by('id')` queue on **every run**, blocking the rotation
  behind it.

`BaseSyncTask`'s three retries over a few minutes were the only attempts such a
company would ever get. `sync_engine.record_orsr_outcome` is now the source's
only writer and the single owner of the outcome → status rule, mirroring
`ruz_financials_sync.sync_company_and_record`: it is called by the Celery task
*and* by both manual drivers (`fetch_orsr_data`, `sync_orsr_filtered`), because
an attempt made by hand is an attempt the gate has to be able to see.

A success is pushed `ANSWERED_RETRY_AFTER` (365 days) into the future. This is
not decoration: `next_retry_at = NULL` reads as "due now" in `sync_due_q`, and
the rotation's retry lane is `companies_due_for_sync('orsr')` — a success that
cleared the field would put all 19 743 already-fetched companies into a lane
sized at a fraction of each batch, and the companies that genuinely need another
attempt would never be reached.

**A visible consequence, measured rather than assumed.** `orsr` rows enter
`sync_state=healthy/failing` and the presets. One induced failure on a company
whose profile had been `fetch_ok=False` since before this change moved
`clean_and_healthy` 275 912 → 275 911 and `sync_state` failing 25 146 →
25 147. The 148 companies with a stored `fetch_ok=False` will each move
`failing` the first time the rotation revisits them — correct, and no longer
invisible.

## The ORSR rotation selected from the head of the queue

`schedule_missing_orsr_sync` chose `orsr_profile__isnull=True … order_by('id')
[:limit]`, exactly as the financials scheduler did before it was fixed. It had
no cursor of its own: it advanced *only* because a successful attempt creates an
`OrsrCompanyProfile`, which removes the company from the population.

So the population it never advanced past was the companies that fail. Measured
over 24 h on the `orsr` worker: **4 626** tasks fetched a profile, **696** ended
permanently failed — 595 RPO transport/DNS failures, 70 `DataError`, 31 scraper
errors. Every one of those wrote no profile and therefore stayed at the head of
an `order_by('id')` queue, re-attempted on every four-hourly run ahead of the
companies nobody had tried yet. A 20-company live batch drew 12 of its 20 from
this pinned set.

The fix is the same shared core the financials rotation now uses,
`sync_engine.rotating_batch`: retries first, capped at `1/RETRY_SHARE` of the
batch, then new ground — and new ground excludes both the companies that have an
attempt recorded *and* the ids already taken as retries, because ORSR's new
ground ("no profile") and its retry lane ("due for a retry") can name the same
company. The status row, not the profile, is the cursor, which is why this
change depends on the section above: before `record_orsr_outcome` existed,
nothing a failing attempt did could move the queue forward.

`schedule_missing_orsr_sync` keeps its name and signature: it is in
`FOCUS_KEEP_TASKS` and is called by name from the beat, the admin `orsr_batch`
action and the legacy dashboard.

**Proved live, not in a test.** Two consecutive batches against the running
stack: the first recorded 20 of 20 attempts, and the second selected a set with
**no overlap at all** with the first. The same canary on the same code before
the worker was restarted recorded 1 of 20 and repeated all 19 — the running
Celery worker still held the pre-change module, which is the trap recorded in
`docs/OBSERVABILITY.md` about the bind mount not being a reload.

## "Neuvedené" is a value, not an absence — fixed in `d2f4e9b`

`RpoSyncService.sync_company` writes `"ico": entity.ico or company.ico` into
`OrsrCompanyProfile.ico`, a `varchar(8)`. The RPO API returns the literal string
`'Neuvedené'` ("not stated") when an entity has no ICO of its own. That string is
truthy, so the `or` never fires and the placeholder is written in place of the
company's own ICO — which the caller already knows and which is always 8 digits.

It fails loudly only by accident: `'Neuvedené'` is **9** characters, one too many
for the column. Measured on two affected companies (`00314404`, `00314072`, both
with a `Pšn/…` registration number): `entity.ico == 'Neuvedené'` and the insert
raises `StringDataTruncation`. In the last 24 h that was **64** permanently
failed tasks on `varying(8)` and **6** on `varying(50)`, where the same
unvalidated mapping writes `_extract_oddiel` into a `varchar(50)`.

**How far it reaches — bounded by measurement, because a rate would have misled
in both directions.** A live 20-company batch drew 12 of its 20 from this cause,
but that batch is the *head* of an `order_by('id')` queue, where the affected
entities cluster; the first full 500-company beat batch that followed recorded 12
of 97 attempts (**~12%**). Neither number is the population. The population is
this: the placeholder tracks the legal form. Of the 2 926 `801` (obec/mesto)
companies in the ORSR-eligible population, 2 839 already hold a profile and 87 do
not — and **6 of 6 sampled from those 87** returned `entity.ico == 'Neuvedené'`,
so for them the upsert can never succeed **and never has**. A 6-company sample of
the 2 483 profile-less `721` (church communities) returned **0 of 6**, so their
missing profiles are ordinary new ground rather than this defect.

The honest bound is therefore **≈ the 87 municipalities with no profile**, plus
isolated cases elsewhere (one `112` s.r.o. is among the 12 measured) — not the
thousands a 12% rate would imply. It is a real ceiling on ORSR coverage for a
known, enumerable set of companies, and every one of them can be named by
querying for a failing `orsr` status row whose `last_error` begins `DataError`.

**The gate cannot see this, by design.** `source_health` fails a source when its
parser recognises *nothing* (`succeeded == 0`), not when some fraction fails — so
ORSR at ~86% success reads `OK` while 87 companies can never be synced at all.
This is not a gap to close by inventing a ratio threshold (`how many items a
source should succeed on depends on the source, so no threshold would be
honest`, as `sync_job_health` already argues for counters). It is why the status
rows this increment added matter: the affected companies are reachable through
`sync_state=failing`, they move `clean_and_healthy`, and they can be listed by
name. The reading that names them is the per-company one, not the per-source one.

Had the placeholder been eight characters or shorter it would have been stored
as if it were data, silently overwriting a correct ICO with "not stated" and
raising nothing — the reason this is worth writing down even though the loud
failure is the harmless version. The same file already knows the convention:
`_person_to_structured` guards `person.identifier != "Neuvedené"` when writing a
person's ICO. The entity ICO has no such guard, and no test covers it.

Stored data is unaffected: these rows were never written.

### The repair, and the half that is not about width

**Falling back, not widening.** The column is right and the mapping is wrong.
Widening `ico` to `varchar(12)` would have made the write succeed and stored
`"Neuvedené"` *as* an IČO — trading a lost profile for a corrupted one that
nothing would ever flag. `OrsrCompanyProfile.save()` already states the
convention, `if not self.ico: self.ico = self.company.ico`; the placeholder's
truthiness was all that kept it from firing.

`RpoSyncService._storable(value, field, ico=…)` now applies both rules to every
column that is a verbatim copy of a source string:

* **the sentinel becomes an absence**, on every such column — including
  `pravna_forma` (`varchar(200)`), where `"Neuvedené"` fits comfortably and
  would have been stored and read as a legal form. This is the half a width
  check cannot reach, and it is the half that matters: the loud failure was the
  harmless version of this defect;
* **a value that does not fit its column is refused, not truncated** — the
  61-character `oddiel` from company 36289's
  `Ministerstvo školstva a národnej osvety v Bratislave No33.121/IV/1929`.
  Truncating would store a string nobody wrote and leave a row that looks
  complete. Widths come from `OrsrCompanyProfile._meta`, so the guard cannot
  drift from the column it guards.

A refusal logs a warning and leaves the raw `registration_number` whole in
`raw_payload.source_register`. Parsing is where that information dies —
`oddiel` is `parts[0]` of it, `vlozka_cislo` is `parts[1]` — so the refusal must
not be the second loss.

**Proved live on company 707** (`00314404`, Obec Bobrov), one of the
profile-less `801` set: `RpoClient` returns `entity.ico == 'Neuvedené'` today,
where the insert used to raise `DataError` and lose the profile. Through the
real task path (`sync_company_orsr_data`) the profile was created for the first
time — `ico = '00314404'`, `obchodne_meno = 'Miestny národný výbor v Bobrove'`,
`oddiel = 'Pšn'`, `vlozka_cislo = '10039'` — with
`raw_payload.source_register.registration_number == 'Pšn/10039/L'`.

Then the whole recorded set was re-attempted, because a fix that works on the
company you picked is not evidence that it works on the population. **11 of 11
succeeded**, every one of them a first-ever profile, and the `DataError` rows
went to **0**. One of the eleven is company 36289 — the `oddiel` overflow, not
the IČO one — and it exercised the other half of the fix on the way through:

```text
WARNING registers.services.rpo_sync: RPO: refusing oddiel for IČO 31988067 --
61 characters do not fit oddiel(50): 'Ministerstvo školstva a národnej
osvety v Bratislave No33.121'
INFO    registers.tasks: Company profile sync OK for company_id=36289 ico=31988067
```

The refusal is a warning and the profile is still written: the unrepresentable
field is dropped, the rest of the profile is not.

**The scraper path is bounded by construction and was left alone.** Its IČO
comes from `OrsrScraper._normalize_ico`, which strips non-digits and zero-fills
to eight; its `oddiel` comes from a `<span class="ra">` table cell matched by
`\S+`. Verified rather than assumed: **0** companies carry an IČO longer than 8
characters, and the widest `oddiel` ever stored is 34 characters against a
column of 50. The defect is specific to RPO, which copies source strings
verbatim.

## The asset side read a four-column table as two

The balance sheet's asset side (šablóna 699, "Strana aktív") has four data
columns: **Brutto**, **Korekcia**, **Netto** for the current period, then the
same for the preceding one. `_extract_with_template` decided how many columns a
table had by asking whether the flattened values were *at least* twice the row
count:

```python
if len(data) >= len(rows) * 2:
    return data[idx * 2]      # "two columns"
```

For a four-column table that test is true and wrong at the same time. The code
then read template row *i* as sheet row `i // 2`, column `2 * (i % 2)`, so
`assets_total` held the **Brutto bežné** of one line and every asset line below
it held another row's value entirely. The label and the number disagreed, and
nothing in the system compared them.

The correct width is not an inference, it is arithmetic: `data` is the table's
values flattened row by row, so it is `rows x columns` long, and the template
declares `pocetDatovychStlpcov`. Measured on 2026-09-12 across **38 tables of 25
companies**: `len(data) == len(rows) * pocetDatovychStlpcov` in **38 of 38**.
The guess was never needed.

### The second instance, in the same file

`_extract_table_total` returned `numbers[-1]` — the last numeric value anywhere
in the flattened table, in whatever column it landed. The tables it serves are
the ones whose *name* matches the revenue/cost/profit keys: "Výnosy" and
"Náklady" (šablóny 696 and 727), four columns wide, where the current period
occupies the first three and the fourth repeats the previous one. Those tables
end in empty "Kontrolné číslo súčet" rows, so the last value found was the last
filled row's **fourth** column — last year's figure, stored as this year's. For
the companies using those templates those two tables are the *only* source of
`revenue` and `costs`, so the wrong number had nothing beside it to contradict
it. Reading down from the bottom for the last non-empty value **in the current
period's column** keeps the original intent (the table's own total row) and
drops the part that was arbitrary.

### Why nothing noticed: a success schedules itself a year out

`ANSWERED_RETRY_AFTER = timedelta(days=365)` (`sync_engine.py:72`): a company
that answers is pushed a year away, so `rotating_batch` would never have
re-read the 696 affected companies. The rotation was working exactly as
designed — which is why the defect needed a deliberate re-sync, not a wait.

The numbers were also wrong in a way no reader could catch. The write gate
(`ruz_financials_sync.py:214`) keeps a statement only when it carries a
`revenue` or a `profit`, so a balance sheet that read a neighbouring column
still arrived as a complete-looking row; and `analysis` is computed on read
(`companies/serializers.py:111`), so there was no stored figure to disagree
with.

The gate was widened later the same day — see *The write gate, closed* below.
That changes which statements are **stored**, not how the statements that are
stored are read, so this measurement stands as it was taken.

### Measured before and after, 2026-09-12

The identity is `assets = equity + liabilities + accruals`, over the rows whose
equity is positive (7 343 before, 7 368 after — the reading changed whether some
rows qualified at all, so both denominators are given).

| | before | after |
|---|---|---|
| Rows where the identity holds | 1 849 / 7 343 = **25.2 %** | 7 104 / 7 368 = **96.4 %** |
| Rows where assets exceed equity + liabilities | 5 458 | **4** |
| Rows with no `assets_total` at all | 39 | **7** |
| Rows more than 10 % of assets out | 66.6 % | **0.0 %** |
| Worst absolute difference | 999 679.64 | **995.58** |
| Worst relative discrepancy | 365 870 % | **2.643 %** |

**Fixed 2026-09-12** (`edc5063`), proved on three levels: 25 unit tests
(including against Postgres in the container), the 38/38 width measurement, and
the live table above.

### The re-sync, and what it cost the registry

`fetch_ruz_financials --ico-file` runs `sync_company_and_record` synchronously —
no Celery, no worker restart, no rate limiter on this path (the `rate_limit` on
the task decorator does not apply). 696 companies: **694 recorded, 2 with no
statements, 0 not in RUZ, 0 unreachable, 10 405 rows written, 0 errors.** No
backup or restore was involved; the volume was not touched.

The selection had to be fixed first: filtering `updated_at__lt=cutoff` *per row*
re-selected forever any company holding one stale unreadable year, re-fetching
its whole history from RUZ on every run. Selecting on
`Max("updated_at")` per company is a correctness fix, not an optimisation —
"we have already read this company" is a fact about the company, not about one
of its years.

### Two templates are now refused that used to be read

`Výdavky` (8) and `Príjmy` (8) — 2 columns, internally consistent shapes — are
refused because their templates carry no header naming the preceding period, so
the current period's column cannot be located. This is a **pre-existing gap for
obec and non-profit accounting**, whose statement is Príjmy/Výdavky rather than
Výnosy/Náklady, and it has **zero field impact**: those names map to no key in
`REVENUE_KEYS`/`COST_KEYS`/`PROFIT_KEYS`, so the old code read them and threw
the result away. They went from read-but-unused to refused. Reported here rather
than papered over.

### Left alone deliberately

A table with **no template at all** keeps the old `numbers[-1]` reading. That is
a different population from the one measured — every table in the 38-table
sample had its template, so nothing is known about how wide a template-less
table is — and refusing there would move a documented outcome as a side effect:
a statement whose every table is unreadable contributes no field, counts as zero
rows, and a *failed template fetch* would then arrive as "this company has no
statements". That is the conflation `UNREACHABLE` was introduced to undo.

### The write gate, closed 2026-09-12

The gate above kept a statement only if it carried `revenue` or `profit`. Read
literally, that discards a statement carrying a readable balance sheet and no
income statement. **Measured 2026-09-12 over 370 statements of 25 companies: the
gate discarded nothing.** Measured again over the whole population in which the
case can appear — every company the rotation attempted and stored no result for,
79 of them — it discarded **one**:

* **00591653** (*PRO-GERS, v.o.s.*) — four statements (2013–2016), each of which
  yields a balance sheet (`assets_total = 328`, `equity = 328`) and neither a
  revenue nor a profit. All four are discarded, so the company stores nothing at
  all. The refusal is the gate's, not the parser's.

**Changed the same day.** The gate now keeps a statement that yielded *any* of
five headline fields — `revenue`, `profit`, `assets_total`, `equity`,
`liabilities_total` (`STATEMENT_HEADLINE_FIELDS`) — rather than a revenue or a
profit specifically. A balance sheet that was read is a measurement, and
discarding it says something about the registry that is not true. `costs` and
`total_revenue` are deliberately not in the tuple: a statement whose `Náklady`
total resolves while `Výnosy` does not is a fragment, and the gate has always
discarded it. The `gated` cause survives, reachable now only by a statement
yielding none of the five.

**Measured after, on the same 79 companies** (`fetch_ruz_financials --ico-file`,
79 selected, 0 not in RUZ, 0 unreachable, 0 errors, 8 rows written):

| the 79 companies | before | after |
|---|---|---|
| store at least one row | 0 | **2** |
| rows stored | 0 | **8** |
| — the gate's doing (`00591653`) | 0 | **4** (2013–2016) |
| — the vocabulary's doing (`00681393`) | 0 | **4** (2022–2025) |
| report `no_statements` | 79 | **77** |

The 77 are the counts the section above already gives: 69 with no statements in
RUZ at all, 5 whose report bodies carry no tables, 3 whose template is entirely
empty. Both companies that moved are the ones that section named by hand — the
gate case and the vocabulary case — which is what makes this a closure rather
than a new measurement.

**One residual, deliberately not claimed as fixed.** `last_detail` is written on
every attempt, but a statement that was read with nothing skipped records an
**empty** string, because the column explains what was *skipped* (two tests hold
that: `registers/tests_financials.py`). So `00591653` — a company that now
stores four rows — carries no detail, exactly as a company never attempted does.
The fact that distinguishes it is in the rows themselves. Making a clean read
persist its own `N of M statement(s) readable` sentence is a one-line change and
a separate decision.

### Four causes, one string

Both companies above were reported the same way, as `NO_STATEMENTS` with the
detail *"N statement(s) present, none readable"*. That string was reached at
`ruz_financials_sync.py` `_read_company` whenever `upserts == 0`, and it was the
same whether

1. the report bodies carry **no tables at all** (`00179027`, and nine of the
   thirteen statements of `00699349`),
2. the bodies carry a template with **every cell empty** (see the second
   correction below),
3. the bodies carry tables **with values**, and no key or column rule maps them
   (`00681393`, `00699349`'s four 1164 statements), or
4. the statements were **read**, and the write gate discarded them (`00591653`).

The fourth is the one that misleads: it says "none readable" about statements
the parser read. The distinction is not cosmetic — it is what decides where a
reader looks. Cases 1 and 2 are the registry having nothing to give; case 3 is a
parser gap; case 4 is a decision this code makes. All four are invisible from the
outside, which is why investigating this took two wrong turns before the reports
themselves were read: an outcome that cannot say *why* it is empty invites the
reader to supply a reason, and the first one supplied was wrong.

**Separated 2026-09-12.** The same sentence reaching all four was itself the
defect, and it is now fixed: `_extract_financials_from_reports` returns an
`ExtractionOutcome` carrying whether any report body had a table (`tables_seen`)
and whether any table held a number this reader could have used (`filled_cells`,
measured with `_to_decimal`, so a cell of prose is not a figure the parser lost),
and `_read_company` splits `skipped` across the four causes. Nothing about what
is *written* changed — the gate, the key vocabulary and the column rules are
untouched — which is why the same four companies produce no stored result after
the change as before it. What changed is that the sentence now names the cause,
and each of the four was verified against the live registry:

| cause | measured company | detail as of 2026-09-12 |
|---|---|---|
| no tables in the bodies | `00179027` | `7 statement(s) present, none recorded (7 with no tables in the report bodies)` |
| template, every cell empty | `00199338` | `1 statement(s) present, none recorded (1 with tables but no filled cell)` |
| values, no field | `00681393`, `00699349` | `13 statement(s) present, none recorded (4 carrying values that yielded no field, 9 with no tables in the report bodies)` |
| read, then gated | `00591653` | `4 statement(s) present, none recorded (4 readable but carrying neither a revenue nor a profit)` |

Three observations from that run are worth keeping. `00699349` and `00681393`
were expected to be different cases and are the **same** one — the sentence
sorted them correctly and the earlier expectation did not, which is the whole
point of the change. The gate case no longer says "none readable" about
statements that were read. And the accounting is per statement but reported per
cause: `00699349`'s one line covers thirteen statements of two different kinds,
which is why the reasons are listed rather than a single cause named.

It matters that this travels in the detail because the outcome is
`NO_STATEMENTS`, which counts as an answered sync and pushes the next attempt out
by `ANSWERED_RETRY_AFTER`: the reason has to ride along, since nothing else about
the run survives — `sync_company_and_record` keeps the detail only for failures
and `CompanySyncStatus.last_error` is therefore empty for every company in this
section. The Celery task logs it (`tasks.py`, `sync_company_financials_from_ruz`), which
is where a scheduled run's reason is visible at all. **Stored durably
2026-09-12** as well: `CompanySyncStatus.last_detail` (migration
`registers/0014`) is written on every attempt — success included, which
`last_error` never is, because a successful attempt blanks it — and read back by
the admin *Stav synchronizácie* page and the `has_detail` filter. Measured after
the 79-company re-sync: 1 250 financials statuses, 78 of them carrying a detail;
the one without is `00591653`, and the reason is in the section above.

### The non-profit statement, measured

`00699349` is *Katolícka jednota Slovenska* — not an obec but a civic body, and
its statement is not Výnosy/Náklady but Príjmy/Výdavky with Majetok/Záväzky.
Its four tables fail for **two different reasons**, and the distinction decides
what a fix would cost:

| table | shape | why it yields nothing |
|---|---|---|
| `Majetok`, `Záväzky` | resolves (`[2, 0]`) | vocabulary: `majetok` and `záväzky` are in neither `BALANCE_SHEET_KEYS` nor the total-label tuples, so recognised rows never become a field |
| `Príjmy`, `Výdavky` | refused (`None`) | no header names the preceding period, so a two-column table has no locatable current period — the same refusal as the two templates above |

The column rule is **not** what fails here, and that was verified against the
header rather than assumed: for šablóna 699 the code picks the right column
(`stlpec 4` = "bežné účtovné obdobie", `stlpec 5` = "bezprostredne
predchádzajúce účtovné obdobie"), and the four-column asset side resolves to
index 2, the cell labelled "netto 2".

**How large it is, measured rather than inferred.** Of 445 626 companies,
**69 906** carry a non-profit or public-sector legal form, and 834 of the 1 250
companies the financials rotation has attempted are in that set — but 824 of
those 834 hold a stored result, which means their statements **read fine**: they
file the ordinary form the parser handles. The gap can only appear where nothing
was stored, because a company that yields no field never gets a row. That
population is **79 companies**, and measured across all of it on 2026-09-12:

| what the 79 did | companies |
|---|---|
| have no statements in RUZ at all | 69 |
| carry statements whose report bodies have no tables | 5 |
| carry a template with every cell empty | 3 |
| carry readable statements the write gate discarded | 1 |
| **carry tables with values and yield no field** — the gap | **1** |

So the gap is one company: `00681393` (*Združenie saleziánov spolupracovníkov*),
four statements on šablóna 1164. That is what "824 of the companies with stored
results are non-profit" does *not* mean, and an earlier version of this section
implied it did. The family is large; the gap inside it is not.

**Closed 2026-09-12.** `majetok` and `zavazky` joined `BALANCE_SHEET_KEYS`,
which is the whole of what was missing: both tables already resolved their
column shape and were discarded before reaching the balance-sheet block that
would have read them. On the 79-company re-sync, `00681393` stored **4 rows**
(2022–2025) where it had stored none:

| year | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| `assets_total` | 265 582.44 | 249 170.60 | 280 263.63 | 239 479.88 |

**The asset side reads and the liability side still does not.** All four rows
carry `assets_total` alone — `equity` and `liabilities_total` are `None`, so
each row is a balance sheet with one side of it. The rows are honest (the API
serves `null` and the page draws `—`), and no ratio is computed from a missing
input, but this is a partial reading and not the statement. What remains is the
`Záväzky` table's own row labels, which yield no total. Recorded here rather
than described as complete.

Two notes on that table. The classification behind it is the measuring script's
own, not the service's — as of 2026-09-12 the service counts the same four causes
itself, so a re-measurement can read them off the run rather than re-deriving
them. And `00699349` is **not** one of the 79: it already holds one stored result,
so it sits in the population above this table (companies with stored results),
which is exactly why its four unreadable statements were visible only by reading
the reports themselves.

**A correction to an earlier version of this section.** It reported that
`00699349`'s reports "do carry tables, and the parser reads none of them",
implying one defect, and attributed it to the municipal vocabulary. Both halves
are now measured and neither is the whole story: nine of its thirteen statements
carry no tables at all, and the four that do fail for the two separate reasons
in the table above.

**A second correction.** An earlier sample counted a statement as a defect
whenever its report bodies carried tables and the parser produced no field —
"has tables" read as "has data". Measured 2026-09-12 over 920 statements of 60
companies: of the 17 that yielded nothing, 12 carried no tables at all and 4
carried a template with **every cell empty** (`neprázdnych = 0`), both correctly
read as nothing. The last one (`00695904`, 2019, šablóna 699) keeps its numbers
in the comparative column: the current-period column is genuinely empty and the
header names the other one, so refusing is right. A body can carry tables and no
data, and the classifier had no bucket for that — which is why the defect rate
it reported (5 in 920) was not real.

**A correction to an earlier version of this section.** It claimed that a
company whose statements all yield nothing "stays at the head of the rotation".
That is wrong twice over. The rotation selects on
`CompanySyncStatus.next_retry_at` (`sync_engine.py:580`), and
`sync_company_and_record` advances that by `ANSWERED_RETRY_AFTER` on every
answered outcome — including `NO_STATEMENTS`, which counts as a success because
the registry *was* read. `updated_at` belongs to `CompanyFinancialResult` and is
not what the rotation reads. A company with unreadable statements is therefore
pushed out a year, exactly like a company with none.

## Two P&L rows shared one field, and the rule that chose between them

`CompanyFinancialResult.profit` was fed by two different rows of the income
statement:

* "Výsledok hospodárenia z hospodárskej činnosti" — the operating result, pre-tax
* "Výsledok hospodárenia za účtovné obdobie po zdanení" — the bottom line, after tax

Both were written with `_pick_better(current, candidate)`, which keeps whichever
has the **larger absolute value**. That rule has no accounting meaning, but it
looked harmless: a profitable company's operating result is larger than its
after-tax result, so the operating row won. A loss, though, *grows* once tax is
deducted — so on a loss-making company the after-tax row won instead.

Meanwhile the field was displayed as **"Zisk po zdanení"** in four places
(`FinancialIndicators.tsx`, `ProfitLossSection.tsx`, `pdfExport.ts`, and the
model's own `verbose_name='Zisk'`). The substitution was therefore invisible.

**Measured 2026-09-12** on the 4 383 rows where a non-zero `income_tax` makes
the two rows distinguishable:

| the row held | count | share |
|---|---|---|
| the pre-tax operating result | 3 788 | 86.4 % |
| the after-tax result | 23 | 0.5 % |
| neither | 572 | 13.1 % |

**All 23 of the after-tax rows were loss-making** — which is the absolute-value
rule, and nothing else. So for 86 % of the rows where the question can be
settled at all, a pre-tax figure was being read as an after-tax one, and on the
loss-makers the arithmetic ran the other way.

### The split, and what is deliberately not back-filled

`profit` is now the operating result and nothing else, and the after-tax row has
its own field. `profit_after_tax` was added in migration
`0016_companyfinancialresult_profit_after_tax`, nullable and **not back-filled**:
a row that has not been re-read since the split genuinely does not carry the
figure, and repeating `profit` under the after-tax label would be the same
substitution in a new place. The screen draws a dash for it, which is the honest
answer.

Three things about the parser are unchanged on purpose, because changing them
would move behaviour nobody asked to move:

* the `PROFIT_KEYS` **table-name** fallback still writes `profit` — a table
  named "Výsledok hospodárenia" is matched by name, not by row label, and it
  gives the same figure the operating row would;
* the computed fallback `profit = revenue - costs` still fills `profit` only.
  That identity *is* the operating result, so it is correct there and must never
  reach `profit_after_tax`;
* `STATEMENT_HEADLINE_FIELDS` still lists `profit` and not `profit_after_tax`, so
  the write gate behaves exactly as before.

### The residual, and where it comes from

The 572 "neither" rows are not explained by this defect. They are dominated by
**pre-2015 statements**, whose older templates the row-label vocabulary does not
match — the table-name fallback fires instead, which is a separate data-quality
gap and is recorded here rather than conflated with the fix.

`update_or_create(defaults={... if v is not None})` skips `None` values, so a
re-sync **cannot** overwrite a row's `profit` with an empty reading, and equally
cannot correct one whose re-parse reads no operating row. Any residue after the
re-sync has to be measured and reported, not assumed away.

### A note on the ratio engine

`ROA` and `ROS` read `fr.profit`, i.e. now consistently the operating result.
Whether they should read the after-tax figure — the conventional choice for a
return ratio — is a **product decision, not taken here**. Switching them now
would blank every ROA and ROS on the site, because `profit_after_tax` is NULL
for every existing row until the re-sync has run. The question is worth
revisiting once its coverage can be measured.

### Scoring models: two computed, four omitted, and why the four are omitted

The six models named for this repository were Altman, IN05, the Kralicek quick
test, the Binkert index, the Index bonity and the Taffler model. Two are
computed and published on the analysis payload; four are not, and the reason is
the same in every case — **the input is not a field**.

| Model | Published | Input it needs |
|---|---|---|
| Altman (1983, private-firm form) | yes | balance sheet, operating result, revenue |
| Taffler (1977, modified form) | yes | the same, plus short-term liabilities and current assets |
| IN05 (Neumaier 2005) | **no** | `nákladové úroky` — interest expense. Not stored. |
| Kralicek quick test (1990) | **no** | cash flow (K2 and K4 are both built on it). Not stored. |
| Index bonity / Binkert | **no** | cash flow (weight 1,5, the heaviest term) and `celkové výkony`. Neither stored. |

The last two rows are **one model under two names**, listed separately because
the plan listed them separately.

This matters beyond a missing feature. IN05's second term is
`EBIT / nákladové úroky`, and its published guidance caps that term at 9 for a
*small* interest charge. That convention says nothing about a charge nobody
read — so substituting the cap would print the most favourable value the term
can take on **every row in this database** and attribute the choice to the
authors. It would also bias every score in the direction of solvency, which is
the dangerous direction for a creditworthiness figure. A constant presented as
a measurement is the exact defect class this document exists to record, so the
model is omitted instead.

Unblocking any of the four is not a computation: it is a **parser and schema
change plus another re-sync**, since interest expense, cash flow and výkony are
read from the statement, not derived. That has not been done.

The Taffler score is the **modified** form,
`ZT = 0,53·X1 + 0,13·X2 + 0,18·X3 + 0,16·X4`, which is the form whose
classification bounds are published (`> 0,3` safe, `0,2–0,3` grey, `< 0,2`
distress). The basic form of the same model differs in X4 and uses a single
bound at zero, so the two are not interchangeable and the score is only
meaningful read as the modified one; the code names the form.

Its X1 numerator is `profit`, the pre-tax operating result — the convention
`financial_analysis` already uses for Altman's X3 (`profit (EBIT approx)`).
Deriving EBT as `profit_after_tax + income_tax` would be arithmetically better
and is deliberately not done: those two fields are only both populated since
the two profit rows were split, so the better derivation would make the Taffler
score unavailable on exactly the rows Altman still scores. **One approximation
applied to both models, stated, beats a second one that is right on some rows
and absent on others.**

Its X2 numerator is the same partial current-asset sum the current ratio and the
sector medians take (see *A note on the ratio engine* above and the field-coverage
measurement below), not a second convention.

Both models are guarded on their inputs being **measured**: an unfiled line
makes the score `None`, never a zero. And both publish their zone as a token
(`zScoreZone`, `tafflerZone`) so no client re-derives a boundary — which is how
`< 1.23` / `< 2.90`, the mirror of the service's ladder, once put exactly 1.23
and exactly 2.90 in the wrong zone on the company page and in the PDF.

### What the re-sync actually filled, measured

Measured **2026-09-12**, after the full re-sync drained (queue at 0, 17:43 UTC).
The corpus is **14 236** `CompanyFinancialResult` rows across **1 173**
companies and **445 626** `Company` rows. Every figure below is a count over
that corpus, reproducible by walking it; none is an estimate.

**`profit_after_tax`.** The field was added by migration `0016` with no
backfill, so before this re-sync it was NULL on every row.

| | rows | share |
|---|---|---|
| after-tax figure filled | **3 661** | 25.7 % |
| `profit` present, after-tax still NULL | **10 521** | 73.9 % |
| neither figure present | 54 | 0.4 % |
| after-tax present, `profit` absent | 0 | — |

The 3 661 are what the re-sync recovered. **The 10 521 are the residual, and
they are the point of this section:** they are not statements without a profit
row — every one of them has `profit` — they are statements whose after-tax row
was not resolved. The split is flat across every year (2019–2025 each land
between 801 and 819 missing against 284–298 filled), which is the signature of
a systematic parse gap rather than of an older template generation.

The stored data cannot say whether the after-tax row is *absent from the
filing* or *present and unmatched by the parser*. That needs a sample of raw
statements, and it has not been done. It is recorded here as the open question
rather than answered by assumption.

**`asset_turnover`.** The row used to be fabricated on any statement whose
`total_revenue` was unread — `_simple_ratio` sent it through `_safe_float` as
`0.0`, and `0.0` falls under the row's `bad` threshold.

| | rows |
|---|---|
| rows where the old code rendered "0.00" | **10 924** (76.7 %) |
| … of those, now showing the filed figure | 10 704 |
| … of those, now showing nothing | 185 |
| … of those, still 0.00 — a *filed* zero revenue | 35 |
| old path produced a number / new path produced a number | 14 144 / 13 959 |

The 35 that still read 0.00 are the distinction this change exists to make: a
filed zero is a measurement and must render, an unread line must not.

**`current_ratio`.** 12 271 rows produce a ratio; 790 rows carry none of the
four current-asset lines. The distribution of how many of the four each row
carries is the finding:

| lines present | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| rows | 790 | 3 455 | **8 851** | 1 070 | **70** |

Only **70 rows (0.5 %)** carry all four lines. The partial sum is therefore not
an edge case — it is how 99.5 % of these ratios are built. That is why it is
documented as deliberate and mirrored in `benchmarking._compute_section_metrics`
rather than tightened unilaterally: the benchmark median beside a company's
ratio is built the same way, so the two agree. Making it strict would blank
almost every current ratio on the site.

**Pre-2015 residual.** 2 132 rows (15.0 %) have `year < 2015`, and 2 127 of
them carry `assets_total`. None is pre-2000. These are the rows whose older
statement templates the row-label vocabulary does not match; they are where the
"neither figure present" 54 and a large part of the after-tax residual live.

**Statements read as a single number.** `00681393` ("Združenie saleziánov
spolupracovníkov na Slovensku") was an open finding: four stored years, each
carrying `assets_total` and nothing else. Measured, it is **35 rows across 16
companies** (0.25 %), spanning 2014–2025, and it is current — 3 rows in 2025.
So it is not one odd company, and it is not a data-model defect: the statement
was read for its headline total and no other line resolved. It is the same
parser gap as the after-tax residual, seen from the other side.

**Scoring-model coverage**, from the same sweep: Altman scores **13 876** rows,
Taffler **12 267**. The 609-row gap between them is the rows that carry no
short-term liability line (1 378 rows lack `liabilities_short` entirely) or no
current-asset line at all. A grep of the model's own fields for interest
expense, cash flow and depreciation returns **nothing** — the four omitted
models have no input to read, which is the finding recorded in the table above.

*The corpus counts in this section were taken at 14 236 rows. The beat-scheduled
incremental financials sync resumed with the stack restart on 2026-09-12, so the
corpus is larger in the two sections below (14 818 and 15 275 at their own
measurement times). Every count here is "as of" and none of them is a ceiling.*

## One ROS denominator, and the sectors where no denominator helps

ROS divided the operating result by **total** revenues. `profit` is "VH z
hospodárskej činnosti" and `revenue` is "Výnosy z hospodárskej činnosti spolu",
so the numerator excluded the financial activity that the denominator included —
and a company earning on its financial side had its ROS understated by whatever
that side contributed. `total_revenue` is also the rarer line by a factor of
four: populated on **3 458** of 15 275 rows against **14 999** for `revenue`.

Both sides of the fraction now read the operating lines, in
`financial_analysis._analyze_year` and in `benchmarking._compute_section_metrics`
— both, because the company's ratio is printed beside `median_ros` and two
different formulas side by side are not a comparison. **11 539 rows gain an
ROS.** At most **22** lose one they had: rows carrying a `total_revenue` with no
operating revenue line under it, which is the scope mismatch this change is
about anyway.

The `SectorBenchmark` rows for 2025 (all 15 of them; the table holds one year)
were regenerated, because they are stored rather than derived on read. All 15
medians moved:

| section | before | after | | section | before | after |
|---|---|---|---|---|---|---|
| A | 2.69 | 3.63 | | N | 1.02 | −3.37 |
| C | 1.85 | 1.64 | | O | — | **−1 159.32** |
| E | — | −679.53 | | P | — | **−1 341.87** |
| F | −32.80 | −11.44 | | Q | 0.84 | −342.91 |
| G | 3.16 | 3.33 | | R | — | −357.60 |
| I | 4.53 | −326.51 | | S | 7.06 | −459.34 |
| J | 21.15 | 21.43 | | H | — | −4.52 |
| L | 1.95 | 1.53 | | M | 4.50 | 1.73 |

**The extreme values are real, and they are confined to the non-market
sections** — E (water), I (accommodation), O (public administration), P
(education), Q (health), R (arts), S (other services). Measured on section O for
2025: 707 rows, **median revenue 18 740 €**, **median costs 604 184 €**, median
`profit` **−578 308 €** — the median entity's operating costs are 32× its
operating revenues. Section O's median ROS is −1 159 % over a sample of 714
companies, so this is not a small-sample artifact, and a denominator floor does
not touch it either (`|revenue| ≥ 100 000 €` leaves the median at −904 %).

The cause is deliberate and already documented in the parser: `Príjmy` and
`Výdavky`, the public-sector statement's two sides, are **not** mapped to
`revenue`/`costs`, so a municipality's grants and transfers never reach
`revenue` while the whole of its operating cost reaches `costs`. *Mesto Prešov*
is the shape in one line: `revenue` 1 074 721 € against `costs` 91 535 664 €.
The ratio is arithmetically right over the lines we hold, and it says what a
company-style ROS says about a body whose income is not company income.

**Left as it is, deliberately.** The alternatives are worse. Reverting to
`total_revenue` restores a knowingly-mismatched formula and gives up 11 539 rows
to make seven sections quieter. Suppressing the ratio where the statement looks
non-market needs a plausibility heuristic — "costs more than N× revenue" — which
is a guess wearing the same clothes as a measurement, and this file exists to
refuse those. The values reported before were not good either: four of the seven
sections published a dash, and Q, I and S published a median over the handful of
their rows that happened to carry both lines.

What would actually fix it is reading the public-sector statement, which is the
same parser project recorded in *The non-profit statement, measured* above, and
it is not a ratio change.

## The balance-sheet control, measured a second time

The company page's one check that needs no second source is the identity
`assets = equity + liabilities + accruals`, with a tolerance of one euro. The
instinct on reading it is that an absolute euro is absurdly strict for a balance
sheet in the millions, and that a relative rule (`max(1 €, 0.1 % of assets)`)
would be the professional choice. **Measured, that instinct is wrong**, and the
distribution is what says so. Over the 14 652 rows carrying the figures the
identity needs:

| | rows |
|---|---|
| balances **exactly** | **13 816** (94.3 %) |
| off by under one euro | 1 |
| flagged as not balancing | 835 (5.7 %) |

There is no rounding band. The 835 are not a population of filing-rounding
residuals with a tail: only **276** of them fall within 0.1 % of assets, and
those include a **215 905 €** gap on assets of 347 M € — 0.06 %. A balance sheet
is a list of totals the filer already added up, so its parts match its own total
to the cent; a relative band would launder real errors as rounding and clear a
third of the flags for nothing. The tolerance is unchanged, and the reasoning is
now in the code beside it.

**The defect was elsewhere: an absent "Časové rozlíšenie" made the check
refuse.** `pasivaTotal` returned null unless all four figures were filed, so
2 477 rows reported "Súvahu nemožno overiť". Measured: of the **2 336** rows
carrying assets, equity and liabilities and no accruals line, **2 326 balance
exactly** when the absent accruals count as zero. A line the filer left out of
the template is a line with nothing in it, not a line we failed to read. The
unverifiable set falls from 2 477 to **166** rows:

| missing figure | rows |
|---|---|
| `liabilities_total` | 122 |
| `equity` | 70 |
| `assets_total` | 7 |
| more than one of the three | 30 |

Eight of the 2 336 now get judged and do not balance (0.3 %), which is a smaller
error than the 5.7 % the control already flags outright — and withholding 2 326
correct verdicts to spare 8 is the wrong trade.

The empty state also stopped naming nothing. It printed one flat sentence
listing all four figures including the accruals line; it now names the missing
figure and the years — *"Chýba: vlastné imanie (2021); záväzky spolu (2022)"* —
and the per-year "nedá sa overiť" badge carries the same detail in its tooltip.

**Deliberately not changed, and why it is recorded here instead.**
`debt_ratio` is computed by `_sum_present(liabilities_total,
liabilities_accruals)` in three places (`serializers`, `benchmarking`,
`pdf_report`), so it still answers "unknown" for those same 2 336 rows even
though the same measurement says the absent line is a zero there too. It is left
alone because the per-company figure is compared against the *stored*
`median_debt_ratio`, so changing it means regenerating every benchmark row in
the same pass — a wider change than this one, and one that would move a
published median for every sector. The accruals-is-zero rule is applied where it
verifies a statement, not yet where it feeds a comparison.

## Two RUZ ID lists travelled to a client that read neither

`CompanyDetailSerializer` declared `fields = '__all__'`, so the company payload
carried `id_uctovnych_zavierok` and `id_vyrocnych_sprav` exactly as the register
delivers them: arrays of RUZ's own identifiers. For ESET that is 28 + 18
integers, for Tatra Asset Management 372, on a response that was already 41 896
bytes — and no line of the frontend has ever read either field.

**The claim this section exists to correct.** An earlier review recorded that
both columns are *empty on every row*. That is false, and it was never written
into this document, which is why the measurement is here rather than a
correction. Across all **445 626** rows of `"Companies and SZCO"`:

| | rows | share |
|---|---|---|
| `ID UZ` null | **0** | — |
| `ID UZ` not an array | **0** | — |
| `ID UZ` non-empty | **322 698** | 72,4 % |
| `ID VS` non-empty | **18 621** | 4,2 % |
| longest `ID UZ` / `ID VS` | 372 / 189 | — |

The distinction matters beyond this field: "empty everywhere" would have
justified dropping the columns, and the truth is that the data was real and
being shipped in a shape nothing could use. VOLKSWAGEN SLOVAKIA, a.s. is the
case that made it visible — **37** statement IDs, **15** annual-report IDs, and
**0** years read — and it is why the Účtovné závierky section prints the RUZ
count beside the count we parsed.

**The change.** `Meta` now uses `exclude = ['id_uctovnych_zavierok',
'id_vyrocnych_sprav']` and two `SerializerMethodField`s publish their lengths.
`exclude` and not an explicit `fields` list, deliberately: a serializer may not
set both, and an explicit list turns every future model field into a decision
someone has to remember to make in a second place. A test asserts field by field
that every other key still travels, so the switch cannot quietly narrow the
public payload.

**What a count is not.** `ruz_statements` is the length of the list RUZ sent us.
It is not the number of statements that exist, and it does not correspond
one-to-one to the years we read: there is no year on a RUZ ID and nothing joins
the two lists. Measured, they agree exactly for **1 071** companies, RUZ lists
more than we read for **1 024**, and fewer for **5**. The section therefore
prints both counts and says that they are two counts. A `null` count renders as
"we do not learn it from this response" and never as zero, because zero is a
positive claim about the register.

**Left in place, measured and recorded.** `bank_accounts` is the other raw
JSONField on the same payload — three entries for IČO 00685399 — and the
frontend reads no `bankAccounts` field anywhere either. It stays, and unlike the
ID arrays it is not a join key but the content of a field a reader would
eventually want on the page; it is small, and removing it would settle a product
question (does the company page show accounts?) in a data-hygiene commit. The
next person to touch this serializer should not have to re-measure it.

## The court open data, read before trusting the note that described it

Two sections of the company page carried a reason for not being built, and the
user asked for the reasons to be checked rather than assumed: *"trebalo by
zistit co je obsahom a ako je to dobre spracovane, aby nebol problem so
spracovanim tych dat (napr nekonzistencia)"*. Both reasons were wrong. This is
what replaces them, measured on 2026-09-12 against the live portal, the national
catalogue's SPARQL endpoint, and two real bulk archives (385 KB and 47 MB) whose
records were read field by field.

**What we said and what is true.**

| Our note said | Measured |
|---|---|
| "Bez API" (no API) | A public, unauthenticated, OpenAPI-documented REST API is live at `obcan.justice.sk/pilot/api/ress-isu-service/v3/api-docs` — `numFound` 4 690 793, newest decision issued 11. 9. 2026 |
| "čerstvosť je nerovnomerná" (uneven freshness) | Worse and more specific: the **bulk files stop dead at 2024-05**, and the 7,58 GB aggregate has been frozen since 29. 4. 2019. It is the API that is current, not the files |
| "bez príznaku «toto je platobný rozkaz» … klasifikácia textu" | `forma_rozhodnutia` is a faceted structured field. **Platobný rozkaz: 594 608** records, plus Zmenkový 11 997, Rozkaz na plnenie 1 157, Európsky 55, Šekový 3. One filtered call returns a named company's orders |

The licence claim survived: **CC BY-SA 4.0**, confirmed through the catalogue's
own terms resource (also `personalDataContainmentType = 2`, i.e. the catalogue
flags the dataset as containing personal data). The portal page itself states no
licence at all; the legal basis is vyhláška MS SR č. 482/2011 Z. z.

**The processing problem is not the one we expected.** Both sections were
blocked on a guess about text; they are actually blocked on *identity*. A
decision record has **no IČO and no party field**. `predmet_konania` — the thing
the case is about — exists only inside the full text. Matching a decision to a
company therefore means full-text name matching, and a search for "Slovnaft"
returns 4 472 hits including decisions that merely mention the company. For an
application whose every other join is keyed on IČO, that is the whole difficulty:
we could fill both sections tomorrow and every row would be a claim we cannot
verify. That is the defect class this document exists to catalogue, so the
sections stay empty and now say why.

**Traps recorded so the next attempt does not pay for them again.** The bulk
files and the API publish **two divergent schemas for the same dataset** — bulk
in Slovak snake_case, API in camelCase — and nothing anywhere documents the
correspondence. `datum_vydania_rozhodnutia` is local midnight rendered in UTC
(`2022-06-01T22:00:00Z` for a decision whose own text says 02. 06. 2022), so
naive parsing shifts every date back one day — the same defect class as Finding
C in this repository. `nadpis_rozhodnutia` is empty in 100 % of records read, a
dead field. `oblast_pravnej_upravy` is empty in 28–36 %. Eight records carry
impossible dates, two of them before 1993. The API's date filters **silently
no-op** when given dotted dates (`vydaniaOd=01.01.2020` returns all 4 690 793
records rather than filtering), an invalid `sortProperty` returns HTTP 500, and
the 2016–2018 archives are nested ZIPs while 2019+ are flat shards. The payloads
themselves are clean UTF-8 with no mojibake — the one encoding defect found was
on the ministry's index page, not in the data.

**Left undone deliberately, and it is a product decision, not hygiene.** CC
BY-SA 4.0 is share-alike, and the catalogue flags personal data; a commercial
product that ingests either needs a licensing answer before an engineering one.
That question is the user's, and it is recorded here rather than settled in a
commit.
