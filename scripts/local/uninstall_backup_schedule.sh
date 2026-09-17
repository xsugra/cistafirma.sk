#!/usr/bin/env bash
# Remove the weekly backup schedule.
#
# macOS: unloads the launchd agent and deletes the generated plist.
# Linux: disables the systemd user timer and deletes its units.
#
# Only the schedule is removed. Backups already on disk, the drill and replica
# records, and the replication destination are left untouched -- an uninstall
# must never be able to look like a data-loss event.
set -Eeuo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
# shellcheck source=lib/backup_os.sh
. "$ROOT_DIR/scripts/local/lib/backup_os.sh"

LABEL="sk.cistafirma.backup"

uninstall_launchd() {
    local plist="$HOME/Library/LaunchAgents/$LABEL.plist"

    if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
        launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
        echo "Unloaded launchd agent: $LABEL"
    else
        echo "launchd agent not loaded: $LABEL"
    fi

    if [ -f "$plist" ]; then
        rm -f "$plist"
        echo "Removed $plist"
    else
        echo "No installed plist at $plist"
    fi
}

uninstall_systemd() {
    local unit_dir
    unit_dir=$(scheduler_unit_dir)
    local timer_unit="$unit_dir/$LABEL.timer"
    local service_unit="$unit_dir/$LABEL.service"

    if ! command -v systemctl >/dev/null 2>&1; then
        echo "systemctl not found; removing the unit files only" >&2
    elif systemctl --user disable --now "$LABEL.timer" >/dev/null 2>&1; then
        echo "Disabled systemd user timer: $LABEL"
    else
        echo "systemd user timer not enabled (or no user manager is running): $LABEL"
    fi

    for unit in "$timer_unit" "$service_unit"; do
        if [ -f "$unit" ]; then
            rm -f "$unit"
            echo "Removed $unit"
        else
            echo "No installed unit at $unit"
        fi
    done

    # Reload so the manager forgets the units it just lost, instead of holding a
    # definition that no longer exists on disk.
    systemctl --user daemon-reload >/dev/null 2>&1 || true
}

case "$CISTAFIRMA_OS" in
    macos) uninstall_launchd ;;
    linux) uninstall_systemd ;;
    *)
        echo "ERROR: no backup schedule uninstaller exists for platform '$CISTAFIRMA_OS'." >&2
        exit 1
        ;;
esac
