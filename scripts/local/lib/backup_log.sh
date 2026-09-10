#!/usr/bin/env bash
# Reader for the JSON-lines evidence logs (restore drills, off-site replicas).
#
# Sourced, never executed. The writers live next to the action they record --
# restore_postgres_drill.sh and replicate_postgres_backup.sh -- because each
# writes a different, deliberately typed schema; a generic writer would have to
# guess types. Reading them back, though, is the same job twice, so it is here.

# Print the fields of the last *parseable* record as tab-separated values.
# Lines that cannot be parsed are skipped rather than trusted, so a torn append
# falls back to the previous good record instead of being read as evidence.
# A completely empty result means "no record", and callers fail closed on that.
last_log_fields() {
    local log="$1"
    shift
    python3 - "$log" "$@" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
fields = sys.argv[2:]
if not path.is_file():
    raise SystemExit(0)

last = None
for line in path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        record = json.loads(line)
    except ValueError:
        continue
    if isinstance(record, dict) and record.get("timestamp"):
        last = record

if last:
    print("\t".join(str(last.get(field, "")) for field in fields))
PY
}
