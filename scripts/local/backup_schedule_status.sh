#!/usr/bin/env bash
# Report the state of the weekly backup schedule. Read-only.
#
# macOS reads launchd; Linux reads the systemd user timer. Both report the same
# three things -- is it installed, is it loaded, did it actually run -- because
# those are the three questions the operational gate asks, and a status command
# that answered a different set would let the operator and the gate disagree.
set -Eeuo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
# shellcheck source=lib/backup_os.sh
. "$ROOT_DIR/scripts/local/lib/backup_os.sh"

LABEL="sk.cistafirma.backup"

# Same shape on both platforms: report the last line of each log the job writes,
# so "it ran" can be read directly rather than inferred from a scheduler field.
report_logs() {
    local log_dir
    log_dir=$(log_dir)
    local log
    for log in "$log_dir/backup.out.log" "$log_dir/backup.err.log"; do
        if [ -f "$log" ]; then
            echo "  last line of $(basename "$log"): $(tail -n 1 "$log")"
        fi
    done
}

status_launchd() {
    local plist="$HOME/Library/LaunchAgents/$LABEL.plist"

    if [ ! -f "$plist" ]; then
        echo "Schedule: NOT installed (no plist at $plist)"
        echo "Install it with: make db-backup-schedule-install"
        exit 1
    fi

    echo "Schedule: installed"
    echo "  plist: $plist"

    if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
        echo "  launchd: loaded"
        launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null \
            | grep -E '(state|last exit code|program) =' \
            | sed 's/^[[:space:]]*/    /' || true
    else
        echo "  launchd: NOT loaded (run make db-backup-schedule-install)"
    fi
}

status_systemd() {
    local unit_dir
    unit_dir=$(scheduler_unit_dir)
    local timer_unit="$unit_dir/$LABEL.timer"
    local service_unit="$unit_dir/$LABEL.service"

    if [ ! -f "$timer_unit" ]; then
        echo "Schedule: NOT installed (no timer at $timer_unit)"
        echo "Install it with: make db-backup-schedule-install"
        exit 1
    fi

    echo "Schedule: installed"
    echo "  timer  : $timer_unit"
    if [ -f "$service_unit" ]; then
        echo "  service: $service_unit"
    else
        echo "  service: MISSING ($service_unit) -- the timer cannot start anything"
    fi

    if ! command -v systemctl >/dev/null 2>&1; then
        echo "  systemd: systemctl not found, so the timer's state cannot be read"
    elif ! systemctl --user show -p LoadState "$LABEL.timer" >/dev/null 2>&1; then
        echo "  systemd: NOT reachable ('systemctl --user' has no running user manager)"
    else
        # is-enabled and is-active print their verdict on stdout and signal it in
        # the exit status; only stdout is wanted here, and each is captured once
        # so a failure of either cannot abort the report mid-way.
        local enabled active
        enabled=$(systemctl --user is-enabled "$LABEL.timer" 2>/dev/null || true)
        active=$(systemctl --user is-active "$LABEL.timer" 2>/dev/null || true)
        echo "  systemd: ${enabled:-unknown}${active:+, $active}"

        if [ "$enabled" != "enabled" ] || [ "$active" != "active" ]; then
            echo "    (run make db-backup-schedule-install to enable and start it)"
        fi

        systemctl --user list-timers --all "$LABEL.timer" --no-pager 2>/dev/null \
            | sed -n '2,3p' \
            | grep -v '^$' \
            | sed 's/^[[:space:]]*/    /' || true
    fi
}

case "$CISTAFIRMA_OS" in
    macos) status_launchd ;;
    linux) status_systemd ;;
    *)
        echo "ERROR: no backup schedule status exists for platform '$CISTAFIRMA_OS'." >&2
        exit 1
        ;;
esac

report_logs
