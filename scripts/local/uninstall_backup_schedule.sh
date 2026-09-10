#!/usr/bin/env bash
# Remove the weekly launchd backup agent.
#
# Only unloads the job and deletes the generated plist. Backups already on disk
# (and the replication destination) are left untouched.
set -Eeuo pipefail

LABEL="sk.cistafirma.backup"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
    launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
    echo "Unloaded launchd agent: $LABEL"
else
    echo "launchd agent not loaded: $LABEL"
fi

if [ -f "$PLIST" ]; then
    rm -f "$PLIST"
    echo "Removed $PLIST"
else
    echo "No installed plist at $PLIST"
fi
