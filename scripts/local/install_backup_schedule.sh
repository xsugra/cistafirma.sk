#!/usr/bin/env bash
# Install (or reinstall) the weekly launchd backup agent.
#
# Generates ~/Library/LaunchAgents/sk.cistafirma.backup.plist from the template
# and loads it. Idempotent: re-running replaces the installed copy and reloads.
set -Eeuo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
LABEL="sk.cistafirma.backup"
AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST="$AGENT_DIR/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/CistaFirma"
TEMPLATE="$ROOT_DIR/scripts/local/launchd/$LABEL.plist.in"

if [ ! -f "$TEMPLATE" ]; then
    echo "ERROR: plist template missing: $TEMPLATE" >&2
    exit 1
fi

# launchd runs agents with a minimal PATH. Build a deterministic one instead of
# capturing the login shell's PATH: a login/interactive shell injects terminal
# integration escape sequences (OSC 1337) that would end up inside the plist.
# The base covers python3/shasum/rsync (/usr/bin) and diskutil (/usr/sbin);
# the directory of any required tool living elsewhere is appended.
detected_path="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
for tool in docker python3 shasum rsync diskutil; do
    tool_bin=$(command -v "$tool" 2>/dev/null || true)
    [ -n "$tool_bin" ] || continue
    tool_dir=$(dirname "$tool_bin")
    case ":$detected_path:" in
        *":$tool_dir:"*) : ;;
        *) detected_path="$detected_path:$tool_dir" ;;
    esac
done

escape_sed() {
    printf '%s' "$1" | sed 's/[&|\\]/\\&/g'
}

mkdir -p "$AGENT_DIR" "$LOG_DIR"

sed -e "s|__ROOT_DIR__|$(escape_sed "$ROOT_DIR")|g" \
    -e "s|__PATH__|$(escape_sed "$detected_path")|g" \
    -e "s|__HOME__|$(escape_sed "$HOME")|g" \
    "$TEMPLATE" > "$PLIST"
chmod 644 "$PLIST"

# Reload idempotently (bootout fails harmlessly when the job is not loaded).
launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "Installed launchd agent: $LABEL"
echo "  plist    : $PLIST"
echo "  schedule : weekly, Sunday 03:17 local time"
echo "  logs     : $LOG_DIR/backup.out.log"
echo "  PATH     : $detected_path"
