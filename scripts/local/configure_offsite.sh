#!/usr/bin/env bash
# Write the machine-local off-site backup configuration.
#
# The off-site volume path differs per machine, so it cannot live in the
# repository -- but the weekly launchd job needs it, or it silently reports
# "off-site volume not mounted" and never replicates. This writes the file that
# scripts/local/lib/backup_env.sh reads.
#
# The file is *updated*, not clobbered: any other CISTAFIRMA_* setting already
# in it (for example the temporary CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP
# exception) is preserved.
#
# The OpenPGP recipient of the off-site replica is recorded here too, and for the
# same reason: it is per-machine (the host that replicates needs the public key,
# the host that restores needs the private one) and the scheduled job has no
# environment to pass it in. It is optional as an argument but not as a
# configuration -- replication refuses to run without it, because the alternative
# would be writing the database off-host in the clear.
set -Eeuo pipefail

KEY="CISTAFIRMA_OFFSITE_BACKUP_DIR"
EXCEPTION_KEY="CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP"
RECIPIENT_KEY="CISTAFIRMA_OFFSITE_GPG_RECIPIENT"

if [ "$#" -lt 1 ] || [ "$#" -gt 3 ]; then
    echo "Usage: $0 /absolute/path/to/offsite/dir [true|false] [recipient]" >&2
    echo "  The optional second argument sets $EXCEPTION_KEY." >&2
    echo "  The optional third sets $RECIPIENT_KEY (a key id or fingerprint)." >&2
    echo "  Omit either (or pass an empty string) to leave that key untouched." >&2
    exit 64
fi

target=$1
allow_unencrypted="${2:-}"
recipient="${3:-}"

case "$allow_unencrypted" in
    ''|true|false) ;;
    *)
        echo "ERROR: the second argument must be 'true' or 'false', got '$allow_unencrypted'" >&2
        exit 64
        ;;
esac

case "$target" in
    /*) ;;
    *)
        echo "ERROR: the off-site directory must be an absolute path: $target" >&2
        exit 64
        ;;
esac

if [ ! -d "$target" ]; then
    echo "ERROR: not a directory — is the volume mounted? $target" >&2
    exit 1
fi

target=$(cd "$target" && pwd -P)

config="${CISTAFIRMA_BACKUP_CONFIG:-$HOME/.config/cistafirma/backup.env}"
config_dir=$(dirname "$config")

mkdir -p "$config_dir"
chmod 700 "$config_dir"

tmp=$(mktemp "$config_dir/.backup.env.XXXXXX")
trap 'rm -f "$tmp"' EXIT

umask 077

if [ -f "$config" ]; then
    # Rewrite the keys we own in place, leave every other line -- comments and
    # unrelated CISTAFIRMA_* settings -- exactly as it was.
    #
    # The exception and recipient keys are guarded on their *value*, not on the
    # key name: an omitted (empty) argument means "leave this key as it is", as
    # the usage text promises. Guarding on the key name instead -- which is
    # never empty -- blanked an already-recorded recipient on every run that
    # passed only the directory, and silently stopped replication, because
    # replication refuses to write an unencrypted replica without one.
    awk -v key="$KEY" -v val="$target" \
        -v ekey="$EXCEPTION_KEY" -v evalue="$allow_unencrypted" \
        -v rkey="$RECIPIENT_KEY" -v rvalue="$recipient" '
        BEGIN { replaced = 0; replaced_exception = 0; replaced_recipient = 0 }
        $0 ~ "^[[:space:]]*" key "=" { print key "=" val; replaced = 1; next }
        evalue != "" && $0 ~ "^[[:space:]]*" ekey "=" {
            print ekey "=" evalue
            replaced_exception = 1
            next
        }
        rvalue != "" && $0 ~ "^[[:space:]]*" rkey "=" {
            print rkey "=" rvalue
            replaced_recipient = 1
            next
        }
        { print }
        END {
            if (!replaced) print key "=" val
            if (evalue != "" && !replaced_exception) print ekey "=" evalue
            if (rvalue != "" && !replaced_recipient) print rkey "=" rvalue
        }
    ' "$config" > "$tmp"
else
    {
        echo "# CistaFirma backup configuration — machine-local, never committed."
        echo "# Written by: make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR=<dir>"
        echo "# Read by scripts/local/lib/backup_env.sh, which the backup scripts source."
        echo "# An exported variable of the same name overrides the value below."
        echo "$KEY=$target"
        if [ -n "$allow_unencrypted" ]; then
            echo "$EXCEPTION_KEY=$allow_unencrypted"
        fi
        if [ -n "$recipient" ]; then
            echo "$RECIPIENT_KEY=$recipient"
        fi
    } > "$tmp"
fi

chmod 600 "$tmp"
mv "$tmp" "$config"
trap - EXIT

echo "Off-site configuration written: $config"
echo "  $KEY=$target"
if [ -n "$allow_unencrypted" ]; then
    echo "  $EXCEPTION_KEY=$allow_unencrypted"
else
    echo "  $EXCEPTION_KEY left unchanged (pass 'true' or 'false' to set it)"
fi
if [ -n "$recipient" ]; then
    echo "  $RECIPIENT_KEY=$recipient"
else
    echo "  $RECIPIENT_KEY left unchanged (pass a key id or fingerprint to set it)"
fi
