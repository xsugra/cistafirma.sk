#!/usr/bin/env bash
# Report the state of the weekly launchd backup agent. Read-only.
set -Eeuo pipefail

LABEL="sk.cistafirma.backup"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/CistaFirma"

if [ ! -f "$PLIST" ]; then
    echo "Schedule: NOT installed (no plist at $PLIST)"
    echo "Install it with: make db-backup-schedule-install"
    exit 1
fi

echo "Schedule: installed"
echo "  plist: $PLIST"

if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
    echo "  launchd: loaded"
    launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null \
        | grep -E '(state|last exit code|program) =' \
        | sed 's/^[[:space:]]*/    /' || true
else
    echo "  launchd: NOT loaded (run make db-backup-schedule-install)"
fi

for log in "$LOG_DIR/backup.out.log" "$LOG_DIR/backup.err.log"; do
    if [ -f "$log" ]; then
        echo "  last line of $(basename "$log"): $(tail -n 1 "$log")"
    fi
done
