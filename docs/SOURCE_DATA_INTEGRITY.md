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

### A transport failure reads as the end of the list

The RUZ import loop ends at `fetch_ruz_data.py:206`, on `if not id_data or not
id_data.get('id')`, logging `No more company IDs to fetch.`.

Every `get_*` method in `backend/registers/integrations/ruz_api.py` catches
`requests.exceptions.RequestException` and returns `None`, which is
indistinguishable from a genuine "not found" at this point. A network failure
therefore ends the loop, and the code below it then runs `progress.complete()`
and `complete_job(job)` — marking the whole sync `completed` on a truncated run.

This is **latent, not demonstrated**: the fail-open line `No more company IDs to
fetch.` occurs **0 times** in the retained worker logs, while the legitimate
`Reached the end of the list.` occurs once. It is recorded here as a known,
unfixed risk rather than a closed one — one transient failure at the wrong
moment would silently truncate a run and store it as a success.

### The incremental cursor only ever moves forward

`fetch_ruz_data.py:253` sets `pokracovat_za_id = company_ids[-1]` after each
page and reads it back from `progress.last_processed_ruz_id`, so the cursor only
ever moves **forward**; `zmenene_od` is read from the stored
`progress.zmenene_od` (`fetch_ruz_data.py:157`), which is frozen at
**2026-08-04** and never advanced.

A live API probe confirmed the consequence is structural, not theoretical: with
`zmenene_od=2026-08-04` and no cursor the API returns changed companies starting
from RUZ ID 66, but with the cursor applied it returns only IDs above the
cursor. A company whose RUZ ID is below the cursor is therefore never re-fetched
by this sync again, even when its data changes. Known limitation, undecided.

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
the write, and `registers.services.sync_engine.record_unreadable_field` records
that refusal against the source as a `CompanySyncStatus` row
(`source='ruz'`, `error_type='parse_error'`, no success). That is what puts it
inside `make ops-check`'s reach:

| Unreadable dates in the window | `source_health` verdict |
|---|---|
| fewer than `CISTAFIRMA_SOURCE_MIN_ATTEMPTS` (200) | counted and shown, **not judged** |
| 200 or more | **FAIL**, and `make ops-check` goes red |

The threshold is inherited, not tuned for RUZ, and it keeps its meaning: a lone
malformed record is an upstream typo and must not hold the gate red forever, or
the alarm stops being read. The cost is that a *slow* trickle takes longer than
a day to reach 200 refusals — which is why the `ERROR` log and the count in the
gate table both exist alongside the verdict.

**A `ruz` row does not mean what a `vszp` row means, so it is not rendered as
one.** `vszp` and `social` write a row per company *attempt*, carrying whether
it succeeded; `ruz` writes one only when a date went unread, and never writes a
success. In the shared table that reads `200 attempts, 0 succeeded` — false in
both halves, since RUZ syncs fine and reads every field except the one, and
since `succeeded` there would mean "not recorded" rather than "none succeeded".
`source_health` therefore renders refusals in their own row kind
(`FIELD_REFUSAL_SOURCES`), with their own wording:

```
  ruz                  200 record(s) carried an unreadable date field  FAIL
  (source 'ruz': 200 record(s) carried a date field that could not be read --
   the source's shape has changed. The affected values were kept, not
   overwritten, so the stored data is stale rather than gone.)
```

Nothing writes `ruz` health rows otherwise, so RUZ appears in that output only
when something is wrong. `record_unreadable_field` deliberately does **not**
route through `update_company_status`: that function models an *attempt*, and a
failure there increments `consecutive_failures` and pushes `next_retry_at`
towards its 24 h cap. A refused field is not an attempt, and since no success
row is ever written for this source the count could never reset — a trap for
whatever first reads those two columns, which today nothing does.

**The gate sees a refusal; the admin surfaces do not.** Leaving
`consecutive_failures` at 0 keeps a trap from arming, but that column is what
every *judging* reader keys on, and nothing replaced it. Read at each site:

| Reader | Keys on | Sees a refused date? |
|---|---|---|
| `adminapi/views/dashboard.py:39` `failures_24h` | `consecutive_failures__gt=0` | no |
| `adminapi/views/dashboard.py:97-104` per-source card | `last_succeeded_at__isnull=False`, `consecutive_failures__gt=0` | no |
| `adminapi/services/company_filters.py:265,426` `sync_state=failing` | `consecutive_failures__gt=0` | no |
| `lead_scoring/services/scoring.py:178-180` | `Avg(consecutive_failures)` | no |

So the gate tells you **how many** records carry an unreadable date, and no
surface lets you find **which** ones. The root is one level below the columns:
`grep -rn SOURCE_RUZ backend/` returns two write sites, both
`record_unreadable_field`. There is no success path for this source, so
`last_succeeded_at` has never once been written for `ruz` and nothing can clear
a refusal. That is also why the admin's `ruz` card reads "0 % coverage, 0
failing" — self-contradictory, and it read that before any of this existed;
these rows did not break it, they made it visible.

**Not fixed here, and the reason is cost, not doubt.** Making the signal real
means giving the source a success path, which means a write on the RUZ bulk
sync — a run that touches every one of 441 714 companies — and it changes every
aggregate above at once. That is a design change with a production write cost,
so it is named as a gap and left for a decision rather than folded into a
correctness fix.

One gap, deliberately recorded rather than hidden: `CompanySyncStatus` keys to
`Company`, and RUZ also writes SZCO records to `IndividualEntity`. A refused
date on an individual is logged but **counted nowhere**, so the gate does not
cover that third of the RUZ surface. It is not covered because there is no row
to attach it to — a gap in the control, not a claim about the data.

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
