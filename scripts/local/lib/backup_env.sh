#!/usr/bin/env bash
# Shared machine-local backup configuration. Sourced, never executed.
#
# The off-site replica path is machine-specific and therefore must not live in
# the repository. It has to be available to the *scheduled* job in particular:
# `scripts/local/scheduled_backup.sh` is started by launchd with an almost empty
# environment, so without this file the weekly run reports
# "off-site volume not mounted; replica skipped" forever -- which reads like a
# hardware problem but actually means "nobody told me where the volume is".
#
# Precedence: a variable already present in the *exported* environment wins, so
# one-off overrides keep working:
#
#     make db-offsite-status CISTAFIRMA_OFFSITE_BACKUP_DIR=/tmp/whatever
#
# Everything else comes from $CISTAFIRMA_BACKUP_CONFIG (default
# ~/.config/cistafirma/backup.env), a plain KEY=VALUE file:
#
#     CISTAFIRMA_OFFSITE_BACKUP_DIR=/Volumes/Verbatim/cistafirmaBackups
#
# Blank lines and `#` comments are ignored, one layer of surrounding quotes is
# stripped, and only CISTAFIRMA_* keys are ever set -- so a stray line cannot
# inject an arbitrary variable into the backup scripts.

CISTAFIRMA_BACKUP_CONFIG="${CISTAFIRMA_BACKUP_CONFIG:-$HOME/.config/cistafirma/backup.env}"

if [ -f "$CISTAFIRMA_BACKUP_CONFIG" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            '' | '#'*) continue ;;
            *=*) ;;
            *) continue ;;
        esac

        key=${line%%=*}
        value=${line#*=}
        key=$(printf '%s' "$key" | tr -d '[:space:]')

        case "$key" in
            CISTAFIRMA_*) ;;
            *) continue ;;
        esac

        case "$value" in
            \"*\")
                value=${value#\"}
                value=${value%\"}
                ;;
            \'*\')
                value=${value#\'}
                value=${value%\'}
                ;;
        esac

        # `printenv` tests the exported environment specifically, which is what
        # matters here: the child processes these scripts spawn inherit only
        # exported variables, so an unexported shell variable would not reach
        # them anyway.
        #
        # An *empty* value counts as unset. `make db-backup-replicate` forwards
        # its make variables unconditionally, so an unset
        # CISTAFIRMA_OFFSITE_BACKUP_DIR arrives as an empty exported string
        # rather than as nothing at all -- and an empty string carries no
        # configuration, so the file must still be able to fill it in.
        if [ -z "$(printenv "$key" 2>/dev/null || true)" ]; then
            export "$key=$value"
        fi
    done < "$CISTAFIRMA_BACKUP_CONFIG"
fi
