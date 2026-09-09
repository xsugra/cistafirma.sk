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
