#!/usr/bin/env bash
# Time helpers shared by the backup status scripts.
#
# Sourced, never executed. Two consumers need these (offsite_status.sh and
# ops_check.sh), which is where a private copy stops being cheaper than a
# shared one. macOS `date` has no portable "age in days" flag, hence python3.

# Whole days since the file was last modified. Prints -1 for a missing file.
age_days() {
    python3 - "$1" <<'PY'
import os
import sys
import time

try:
    mtime = os.path.getmtime(sys.argv[1])
except OSError:
    print(-1)
    raise SystemExit(0)

print(int((time.time() - mtime) // 86400))
PY
}

# Whole days since an ISO-8601 timestamp. Prints -1 when it cannot be parsed,
# so a caller can tell "old" from "unreadable" and fail closed on the latter.
iso_age_days() {
    python3 - "$1" <<'PY'
import sys
from datetime import datetime, timezone

raw = sys.argv[1].strip()
# A trailing Z is only accepted by fromisoformat from 3.11 on, and this runs
# from launchd with whatever python3 is on that PATH, so normalise it here.
if raw.endswith(("Z", "z")):
    raw = raw[:-1] + "+00:00"

try:
    stamp = datetime.fromisoformat(raw)
except ValueError:
    print(-1)
    raise SystemExit(0)

if stamp.tzinfo is None:
    stamp = stamp.replace(tzinfo=timezone.utc)

print(int((datetime.now(timezone.utc) - stamp).total_seconds() // 86400))
PY
}
