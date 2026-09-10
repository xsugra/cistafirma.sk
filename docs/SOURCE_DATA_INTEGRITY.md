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
