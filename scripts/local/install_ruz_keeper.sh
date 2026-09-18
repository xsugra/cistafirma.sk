#!/usr/bin/env bash
# Install (or reinstall) the RUZ full-resync keeper on a Linux production host.
#
# A systemd *user* timer + oneshot service, generated from
# scripts/local/systemd/sk.cistafirma.ruz-keeper.*.in, that runs one
# `ruz_keeper_tick` every five minutes. Idempotent: re-running replaces the
# installed units and reloads them.
#
# Linux only, and deliberately so: the keeper exists to restart a walk that
# production needs finished, and production is `dell`. Installing it on a
# developer machine would give that machine a timer that dispatches Celery tasks
# at whatever stack happens to be running there.
#
# Why a host timer and not a Celery beat entry: the keeper recovers the stack
# from a state Celery is already in. On the `celery` beat queue it would stop
# exactly when it is needed -- a wedged worker, or a `PeriodicTask` row that no
# longer matches `CELERY_BEAT_SCHEDULE`, which this repository has been bitten by
# before. The one log gate here is the one that must not depend on the thing it
# watches.
set -Eeuo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
# shellcheck source=lib/backup_os.sh
. "$ROOT_DIR/scripts/local/lib/backup_os.sh"

# The same name for the systemd unit prefix as the backup job uses, so "the
# keeper" needs no per-job name table.
LABEL="sk.cistafirma.ruz-keeper"

escape_sed() {
    printf '%s' "$1" | sed 's/[&|\\]/\\&/g'
}

# A deterministic PATH built from a base plus the directory of each tool the job
# needs, rather than the login shell's PATH -- an interactive shell injects
# terminal escape sequences that would land inside the generated unit file.
# Missing tools are skipped here on purpose: their absence has to surface as a
# failed tick with a nameable cause, not as an installer that refuses to install.
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

if [ "$CISTAFIRMA_OS" != "linux" ]; then
    echo "ERROR: the RUZ keeper installs on Linux only (detected: $CISTAFIRMA_OS)." >&2
    echo "       It belongs on the host that runs production, which is \`dell\`." >&2
    exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
    echo "ERROR: systemctl not found, so there is no user manager to schedule with." >&2
    exit 1
fi

unit_dir=$(scheduler_unit_dir)
service_unit="$unit_dir/$LABEL.service"
timer_unit="$unit_dir/$LABEL.timer"
service_template="$ROOT_DIR/scripts/local/systemd/$LABEL.service.in"
timer_template="$ROOT_DIR/scripts/local/systemd/$LABEL.timer.in"

for template in "$service_template" "$timer_template"; do
    if [ ! -f "$template" ]; then
        echo "ERROR: systemd unit template missing: $template" >&2
        exit 1
    fi
done

# A tick that cannot run `docker compose` is a tick that fails every five
# minutes for as long as it is installed -- and a keeper that never dispatches
# looks exactly like a walk that never needs restarting. Ask now, while the
# operator is still watching, instead of letting it be discovered by a walk that
# died and stayed dead. Asks whether docker *works for this user*, not whether
# the `docker` group is listed: rootless and proxied setups are legitimate.
if ! docker info >/dev/null 2>&1; then
    echo "ERROR: 'docker' does not work for ${USER:-this user} on this host, so no" >&2
    echo "       tick could dispatch anything. The timer runs as you (a systemd user" >&2
    echo "       unit), so it inherits exactly this limitation." >&2
    echo "       Most commonly the user is not in the docker group:" >&2
    echo "         sudo usermod -aG docker ${USER:-<user>}   # then log out and back in" >&2
    exit 1
fi

# The failure this check exists for: a user timer only runs while the user has a
# session, so on a headless host without lingering the keeper stops the moment
# the operator logs out -- silently, while `systemctl --user status` still reads
# "waiting". That is the same shape as the incident this whole mechanism is
# about, so it is refused rather than footnoted.
if command -v loginctl >/dev/null 2>&1; then
    linger=$(loginctl show-user "${USER:-$(id -un)}" -p Linger --value 2>/dev/null || true)
    if [ "$linger" != "yes" ]; then
        echo "ERROR: lingering is off for ${USER:-$(id -un)}, so a user timer would stop" >&2
        echo "       at logout -- and a stopped keeper is indistinguishable from a" >&2
        echo "       finished walk. Enable it first, then re-run this installer:" >&2
        echo "         sudo loginctl enable-linger ${USER:-$(id -un)}" >&2
        exit 1
    fi
fi

detected_path=$(detect_path "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    docker python3)
docker_bin=$(command -v docker)

mkdir -p "$unit_dir"

sed -e "s|__ROOT_DIR__|$(escape_sed "$ROOT_DIR")|g" \
    -e "s|__DOCKER__|$(escape_sed "$docker_bin")|g" \
    -e "s|__PATH__|$(escape_sed "$detected_path")|g" \
    -e "s|__HOME__|$(escape_sed "$HOME")|g" \
    "$service_template" > "$service_unit"

sed -e "s|__ROOT_DIR__|$(escape_sed "$ROOT_DIR")|g" \
    "$timer_template" > "$timer_unit"

chmod 644 "$service_unit" "$timer_unit"

# Captured rather than piped: `systemctl --user` needs a live user manager, and
# when it is absent that has to be reported as "the timer could not be loaded"
# instead of escaping as an unexplained non-zero exit.
if ! systemctl --user daemon-reload 2>/dev/null; then
    echo "ERROR: 'systemctl --user' is not usable here (no running user manager)." >&2
    echo "       The unit files were written, but nothing was loaded. Run this from" >&2
    echo "       a login session (or with XDG_RUNTIME_DIR set), then:" >&2
    echo "         systemctl --user enable --now $LABEL.timer" >&2
    exit 1
fi

systemctl --user enable --now "$LABEL.timer"

echo "Installed systemd user timer: $LABEL"
echo "  units    : $timer_unit"
echo "             $service_unit"
echo "  schedule : every 5 minutes, on the wall clock (*:0/5), Persistent=true"
echo "  runs     : cd $ROOT_DIR && $docker_bin compose exec -T backend \\"
echo "               python manage.py ruz_keeper_tick"
echo "  check it : systemctl --user list-timers $LABEL.timer"
echo "             python manage.py ruz_keeper_tick --dry-run   # what it would do"
echo "  logs     : journalctl --user -u $LABEL --since '1 hour ago'"
echo ""
echo "  Stop it once the walk has finished:  systemctl --user disable --now $LABEL.timer"
