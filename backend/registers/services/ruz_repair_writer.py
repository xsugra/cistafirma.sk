"""The one way a repair command stores a RUZ record.

`repair_ruz_sync`, `repair_ruz_sync_v2` and `repair_ruz_gaps` all fetch the
records the database does not hold and store them from a thread pool. Each of
them used to build its own `defaults` dict and upsert it with
`Company.objects.update_or_create(ico=...)`. That is a different writer from the
one the walk uses, and a wrong one; `docs/PLAN.md` §11.9 has the measurement,
the short version is three ways:

* `ico` is not the register's identity. It is `unique`, so when the register
  answers one IČO with a second entity (`00177474` -> ruz_id 1677, 1049449,
  1070716 is the measured example) the lookup finds the **incumbent** row and the
  write re-stamps its `ruz_id` to the new entity's. The entity that was there is
  destroyed, nothing raises, and the run counts the swap as ordinary work.
* a bare `parse_date` reads an unreadable value as `None`, so it overwrites a
  stored date instead of being refused the way `apply_ruz_dates` refuses it.
* nothing routed SZCO legal forms to `IndividualEntity`, so a repair walked over
  the register's natural persons would insert a `Company` row for every one of
  them. Measured on dell 2026-09-18: `IndividualEntity` held 35 339 rows and
  **not one** of their `ruz_id`s was in `Company` -- which is exactly the work
  list these commands build. (The count is a snapshot and only goes up while the
  walk runs; the overlap being zero is the durable half of the measurement.)

So they store through the walk's own writer instead. Same choice, and the same
reason, as `repair_ico_shape._reimport`: a second copy of the field mapping
drifts, and a repair is only correct if it stores what the walk would have
stored.

Two things the walk's writer does not carry, and a repair needs:

* It writes a line per record to `self.stdout` / `self.stderr`. The repair
  commands call it from `ThreadPoolExecutor` with 5-10 workers, so those streams
  are shared. `_OneWriterAtATime` wraps the *stream*, not the call: the database
  work stays parallel and only the operator's view is serialized.
* Its outcomes have to be told apart. A record the register serves without a
  usable IČO is `SKIPPED`; a record the schema refuses is `REFUSED`, and that is
  the one an operator has to look at -- it is usually a second entity under an
  IČO another row already holds, which is a fact to report rather than to resolve
  by overwriting the holder.
"""

import threading

from django.db import DataError, IntegrityError

# What one record's write came to. The caller owns the counters, because the
# three commands count differently (`created` / `repaired`) and only agree on
# what a refusal is.
CREATED = 'created'
UPDATED = 'updated'
SKIPPED = 'skipped'
REFUSED = 'refused'


class _OneWriterAtATime:
    """Serialize writes to a shared stream, and nothing else.

    Deliberately narrow. The point is that ten workers cannot interleave
    half-lines into the operator's view; it is not a lock on the write to the
    database, and holding it around the whole call would serialize exactly the
    parallelism the caller opened a pool for.
    """

    def __init__(self, stream, lock):
        self._stream = stream
        self._lock = lock

    def write(self, message):
        with self._lock:
            self._stream.write(message)

    def flush(self):
        with self._lock:
            self._stream.flush()


class RepairWriter:
    """Store repair records through the walk's writer, safely from threads.

    One instance per run, created on the command's own thread and shared by its
    workers. `update_or_create_company` reads `self.stdout`/`self.stderr` and
    writes to them; it never assigns to `self`, so the instance is safe to share
    and only the streams need the lock.
    """

    def __init__(self, stdout, stderr):
        # Imported here rather than at module level: this module is imported by
        # the repair commands, and `fetch_ruz_data` pulls in the same app's
        # models and services. Keeps the import graph of a management command
        # out of everything that imports a service.
        from registers.management.commands.fetch_ruz_data import Command as Walk

        self._lock = threading.Lock()
        self._walk = Walk(
            stdout=_OneWriterAtATime(stdout, self._lock),
            stderr=_OneWriterAtATime(stderr, self._lock),
        )

    def store(self, ruz_id, details, entity_type='both'):
        """Store one record.

        Returns `(outcome, reason)`, where outcome is CREATED, UPDATED, SKIPPED
        or REFUSED, and reason is non-empty only for REFUSED -- the text belongs
        to the caller, because only the caller can put it on the run's own
        `last_error`.

        `SKIPPED` and `REFUSED` both mean "the database does not hold this
        record now", and they are not the same thing: the first is the register
        declining to serve a usable record, the second is the schema declining to
        take one it did serve. Only the second is a control.
        """
        try:
            created, updated = self._walk.update_or_create_company(details, entity_type)
        except (DataError, IntegrityError) as e:
            # Printed here, beside the walk's own lines, because this is the one
            # outcome an operator watching the run has to see as it happens. The
            # log line and the row are the caller's -- one failure, one of each.
            #
            # Written *without* taking `self._lock`: `self._walk.stderr` is the
            # `_OneWriterAtATime` wrapper, which takes that same lock itself. A
            # `with self._lock:` around this call therefore re-entered a
            # non-reentrant `Lock` and hung the calling thread for ever -- a
            # deadlock, not a slow write, and one that only ever fires on the
            # refusal path, so it would have looked like the repair hanging on a
            # bad record rather than like a bug here.
            reason = f"{type(e).__name__}: {e}"
            self._walk.stderr.write(
                f"RUZ id {ruz_id} ({details.get('ico')!r}) was read but not "
                f"stored -- the database refused it: {reason}"
            )
            return REFUSED, reason

        if not created and not updated:
            # `update_or_create_company` returns this for a record with no usable
            # IČO, having already named the field on stderr.
            return SKIPPED, ''

        return (CREATED if created else UPDATED), ''
