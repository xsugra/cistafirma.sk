#!/usr/bin/env bash
# Install (or reinstall) the weekly backup schedule.
#
# macOS: a launchd LaunchAgent, generated from scripts/local/launchd/*.plist.in
#        into ~/Library/LaunchAgents and bootstrapped into the user's session.
# Linux: a systemd *user* timer + service, generated from
#        scripts/local/systemd/*.in into ~/.config/systemd/user and enabled.
#
# Both are idempotent: re-running replaces the installed units and reloads them.
set -Eeuo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
# shellcheck source=lib/backup_os.sh
. "$ROOT_DIR/scripts/local/lib/backup_os.sh"

# One name for the job on both platforms: the launchd label and the systemd unit
# prefix. Keeping them equal is what lets the status script, the gate and the
# uninstaller talk about "the backup job" without a per-platform name table.
LABEL="sk.cistafirma.backup"

escape_sed() {
    printf '%s' "$1" | sed 's/[&|\\]/\\&/g'
}

# Build a deterministic PATH from a base plus the directory of every tool the
# job needs, rather than capturing the login shell's PATH: a login/interactive
# shell injects terminal integration escape sequences (OSC 1337) that would end
# up inside the generated unit file. Missing tools are skipped here on purpose --
# their absence has to surface as a failed run with a nameable cause, not as an
# installer that refuses to install.
detect_path() {
    local base="$1"
    shift
    local tool tool_bin tool_dir
    for tool in "$@"; do
        tool_bin=$(command -v "$tool" 2>/dev/null || true)
        [ -n "$tool_bin" ] || continue
        tool_dir=$(dirname "$tool_bin")
        case ":$base:" in
            *":$tool_dir:"*) : ;;
            *) base="$base:$tool_dir" ;;
        esac
    done
    printf '%s' "$base"
}

# --- macOS -----------------------------------------------------------------

install_launchd() {
    local agent_dir="$HOME/Library/LaunchAgents"
    local plist="$agent_dir/$LABEL.plist"
    local log_dir
    log_dir=$(log_dir)
    local template="$ROOT_DIR/scripts/local/launchd/$LABEL.plist.in"
    local detected_path

    if [ ! -f "$template" ]; then
        echo "ERROR: plist template missing: $template" >&2
        exit 1
    fi

    # The base covers python3/shasum/rsync (/usr/bin) and diskutil (/usr/sbin);
    # the directory of any required tool living elsewhere is appended.
    detected_path=$(detect_path "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
        docker python3 shasum rsync diskutil)

    mkdir -p "$agent_dir" "$log_dir"

    sed -e "s|__ROOT_DIR__|$(escape_sed "$ROOT_DIR")|g" \
        -e "s|__PATH__|$(escape_sed "$detected_path")|g" \
        -e "s|__HOME__|$(escape_sed "$HOME")|g" \
        "$template" > "$plist"
    chmod 644 "$plist"

    # Reload idempotently (bootout fails harmlessly when the job is not loaded).
    launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
    launchctl bootstrap "gui/$(id -u)" "$plist"

    echo "Installed launchd agent: $LABEL"
    echo "  plist    : $plist"
    echo "  schedule : weekly, Sunday 03:17 local time"
    echo "  logs     : $log_dir/backup.out.log"
    echo "  PATH     : $detected_path"
}

# --- Linux -----------------------------------------------------------------

install_systemd() {
    local unit_dir
    unit_dir=$(scheduler_unit_dir)
    local timer_unit="$unit_dir/$LABEL.timer"
    local service_unit="$unit_dir/$LABEL.service"
    local log_dir
    log_dir=$(log_dir)
    local service_template="$ROOT_DIR/scripts/local/systemd/$LABEL.service.in"
    local timer_template="$ROOT_DIR/scripts/local/systemd/$LABEL.timer.in"
    local detected_path docker_group

    for template in "$service_template" "$timer_template"; do
        if [ ! -f "$template" ]; then
            echo "ERROR: systemd unit template missing: $template" >&2
            exit 1
        fi
    done

    if ! command -v systemctl >/dev/null 2>&1; then
        echo "ERROR: systemctl not found. This branch installs a systemd user timer;" >&2
        echo "       a host without systemd needs a different scheduler (e.g. cron)." >&2
        exit 1
    fi

    # A weekly job that cannot run `docker compose` is a job that fails every
    # week -- which is precisely how the missing replica survived unnoticed on
    # macOS for weeks before the failure marker existed. Ask the question now,
    # while the operator is still watching, instead of letting the first missed
    # run be the discovery.
    #
    # It asks whether docker *works for this user*, not whether the `docker`
    # group is listed in `id`: rootless and proxied docker setups are legitimate
    # and a group check would reject them. The group is the common cause, so it
    # is named in the error.
    if ! docker info >/dev/null 2>&1; then
        echo "ERROR: 'docker' does not work for ${USER:-this user} on this host, so the" >&2
        echo "       weekly job could not make a backup. The timer runs as you (a systemd" >&2
        echo "       user unit, the counterpart of a macOS LaunchAgent), so it inherits" >&2
        echo "       exactly this limitation." >&2
        echo "       Most commonly the user is not in the docker group:" >&2
        echo "         sudo usermod -aG docker ${USER:-<user>}   # then log out and back in" >&2
        exit 1
    fi

    # The base is the standard Linux path set; docker/python3/rsync may live in
    # /usr/local/bin (a manual install) and the rest are coreutils or util-linux.
    detected_path=$(detect_path "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
        docker python3 sha256sum rsync findmnt lsblk cryptsetup ssh base64 notify-send)

    mkdir -p "$unit_dir" "$log_dir"

    sed -e "s|__ROOT_DIR__|$(escape_sed "$ROOT_DIR")|g" \
        -e "s|__PATH__|$(escape_sed "$detected_path")|g" \
        -e "s|__HOME__|$(escape_sed "$HOME")|g" \
        -e "s|__LOG_DIR__|$(escape_sed "$log_dir")|g" \
        "$service_template" > "$service_unit"

    sed -e "s|__ROOT_DIR__|$(escape_sed "$ROOT_DIR")|g" \
        "$timer_template" > "$timer_unit"

    chmod 644 "$service_unit" "$timer_unit"

    # Captured rather than piped: `systemctl --user` needs a live user manager,
    # and when it is absent the error has to be reported as "the timer could not
    # be loaded" instead of escaping as an unexplained non-zero exit.
    if ! systemctl --user daemon-reload 2>/dev/null; then
        echo "ERROR: 'systemctl --user' is not usable here (no running user manager)." >&2
        echo "       The unit files were written, but nothing was loaded. Run this from a" >&2
        echo "       login session (or with XDG_RUNTIME_DIR set), then:" >&2
        echo "         systemctl --user enable --now $LABEL.timer" >&2
        exit 1
    fi

    systemctl --user enable --now "$LABEL.timer"

    if id -nG 2>/dev/null | tr ' ' '\n' | grep -qx docker; then
        docker_group="yes"
    else
        docker_group="no (docker still works for this user, so this is fine)"
    fi

    echo "Installed systemd user timer: $LABEL"
    echo "  units    : $timer_unit"
    echo "             $service_unit"
    echo "  schedule : weekly, Sunday 03:17 local time (Persistent=true, so a missed run is caught up)"
    echo "  logs     : $log_dir/backup.out.log (and the unit's journal)"
    echo "  PATH     : $detected_path"
    echo "  docker   : group membership: $docker_group"
    # A user timer only runs while the user has a session unless lingering is
    # enabled. On a headless server that is the difference between a working
    # schedule and a silent one, so it is stated rather than assumed -- but not
    # done here: it changes machine-wide login state, not this repository.
    echo "  note     : user timers stop when your last session ends. For a headless"
    echo "             server, run once:  sudo loginctl enable-linger ${USER:-<user>}"
}

case "$CISTAFIRMA_OS" in
    macos) install_launchd ;;
    linux) install_systemd ;;
    *)
        echo "ERROR: no backup schedule installer exists for platform '$CISTAFIRMA_OS'." >&2
        exit 1
        ;;
esac
