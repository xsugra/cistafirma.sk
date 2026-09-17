#!/usr/bin/env bash
# Read-only off-site backup readiness report.
#
# Never writes anything, never starts a container and never touches the
# database. Exits non-zero when a required control is unmet, so it can gate
# CI or a health check.
set -Eeuo pipefail

# Machine-local off-site configuration; an already exported variable wins, so
# `make db-offsite-status CISTAFIRMA_OFFSITE_BACKUP_DIR=...` still overrides.
# Must precede the CISTAFIRMA_* defaults read just below.
LIB_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib
# shellcheck source=lib/backup_env.sh
. "$LIB_DIR/backup_env.sh"
# shellcheck source=lib/backup_time.sh
. "$LIB_DIR/backup_time.sh"
# shellcheck source=lib/backup_log.sh
. "$LIB_DIR/backup_log.sh"
# shellcheck source=lib/backup_os.sh
. "$LIB_DIR/backup_os.sh"
# shellcheck source=lib/offsite_crypto.sh
. "$LIB_DIR/offsite_crypto.sh"
# shellcheck source=lib/backup_gpg.sh
. "$LIB_DIR/backup_gpg.sh"

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
STATE_DIR=$(state_dir)
DEFAULT_BACKUP_DIR="$STATE_DIR/backups"
BACKUP_DIR="${CISTAFIRMA_BACKUP_DIR:-$DEFAULT_BACKUP_DIR}"
MAX_AGE_DAYS="${CISTAFIRMA_BACKUP_MAX_AGE_DAYS:-7}"
DRILL_LOG="${CISTAFIRMA_DRILL_LOG:-$STATE_DIR/restore_drills.log}"
MAX_DRILL_AGE_DAYS="${CISTAFIRMA_DRILL_MAX_AGE_DAYS:-30}"
REPLICA_LOG="${CISTAFIRMA_REPLICA_LOG:-$STATE_DIR/replicas.log}"
MAX_REPLICA_AGE_DAYS="${CISTAFIRMA_REPLICA_MAX_AGE_DAYS:-14}"
REQUIRE_MOUNTED="${CISTAFIRMA_OFFSITE_REQUIRE_MOUNTED:-true}"

failures=0
warnings=0
ok() { printf 'OK    %s\n' "$*"; }
warn() {
    printf 'WARN  %s\n' "$*"
    warnings=$((warnings + 1))
}
bad() {
    printf 'FAIL  %s\n' "$*"
    failures=$((failures + 1))
}

# "The volume is not attached" is a documented normal state -- DATA_PROTECTION.md
# says to keep it disconnected except while replicating -- so an unattended run
# must not call it a failure, or the weekly alert turns into noise that everyone
# learns to ignore. A deliberate `make db-offsite-status` keeps the strict
# default: when you ask by hand you want the truth, not the policy.
unmounted() {
    if [ "$REQUIRE_MOUNTED" = "true" ]; then
        bad "$1"
    else
        warn "$1 (not required for an unattended run)"
    fi
}

read_sha256() {
    python3 - "$1" <<'PY'
import json
import sys
from pathlib import Path

print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["sha256"])
PY
}

plain_checksum() {
    sha256_of "$1"
}

printf 'CistaFirma off-site backup status\n'
printf '  local backup dir : %s\n' "$BACKUP_DIR"
printf '  off-site dir     : %s\n' "${CISTAFIRMA_OFFSITE_BACKUP_DIR:-<not set>}"
printf '  max backup age   : %s day(s)\n\n' "$MAX_AGE_DAYS"

# --- newest local backup -------------------------------------------------
newest=""
if [ -d "$BACKUP_DIR" ]; then
    newest=$(ls -1 "$BACKUP_DIR"/cistafirma_*.dump 2>/dev/null | LC_ALL=C sort | tail -n 1 || true)
fi

if [ -z "$newest" ]; then
    bad "no local backup found in $BACKUP_DIR"
else
    days=$(age_days "$newest")
    printf '  newest dump      : %s (%s day(s) old)\n' "$(basename "$newest")" "$days"
    if [ "$days" -gt "$MAX_AGE_DAYS" ]; then
        bad "newest local backup is ${days} day(s) old (limit ${MAX_AGE_DAYS})"
    else
        ok "newest local backup is fresh (${days} day(s) old)"
    fi

    manifest="${newest}.json"
    if [ ! -f "$manifest" ]; then
        bad "manifest missing: $(basename "$manifest")"
    elif [ "$(read_sha256 "$manifest")" = "$(plain_checksum "$newest")" ]; then
        ok "newest local backup checksum matches its manifest"
    else
        bad "checksum mismatch for $(basename "$newest")"
    fi
fi

# --- off-site replica ----------------------------------------------------
printf '\n'
offsite="${CISTAFIRMA_OFFSITE_BACKUP_DIR:-}"

# The reference for "is this a different filesystem": the directory the local
# dumps are written to, with $HOME standing in when there is no local backup
# directory yet -- both are on the disk the off-site copy must not share, and a
# reference that does not exist would refuse a perfectly good destination.
offsite_reference="$BACKUP_DIR"
[ -d "$offsite_reference" ] || offsite_reference="$HOME"

if [ -z "$offsite" ]; then
    unmounted "CISTAFIRMA_OFFSITE_BACKUP_DIR is not set — no off-site replica is possible"
elif ! cistafirma_offsite_mount_check "$offsite" "$offsite_reference"; then
    # The verdict, not the path, decides. A configured destination that is not
    # attached is reported as exactly that, never silently skipped past into
    # "no replica of the newest dump" -- which reads like a stale copy rather
    # than an unreachable destination, and sends the operator after the wrong
    # problem. See cistafirma_offsite_mount_check for what is measured.
    if [ "$CISTAFIRMA_OFFSITE_MOUNT_VERDICT" = "same-filesystem" ]; then
        # Not a mounting problem: the path is real, it is simply on this
        # machine's own disk, and the fix is the configuration.
        bad "off-site directory is on the same filesystem as the local backup: $offsite"
    elif [ "$CISTAFIRMA_OS" = "macos" ]; then
        # Kept word for word: the line production has always printed.
        unmounted "off-site directory is not mounted: $offsite"
    else
        unmounted "off-site directory is configured but not mounted: $offsite (${CISTAFIRMA_OFFSITE_MOUNT_REASON})"
    fi
else
    offsite=$(cd "$offsite" && pwd -P)
    ok "off-site directory is mounted: $offsite"

    if [ -n "$newest" ] && [ "$(device_id_of "$(dirname "$newest")")" = "$(device_id_of "$offsite")" ]; then
        bad "off-site directory is on the same filesystem as the local backup"
    else
        ok "off-site directory is on a different filesystem"
    fi

    # --- the artifact is the control -------------------------------------
    #
    # What is judged here is the replica itself, not the volume it sits on: the
    # dump is encrypted at source, before it is written, so the destination's own
    # encryption stopped being the thing that protects it. Every question below
    # is asked of the file and of the manifest written beside it, and none of
    # them needs a private key -- which is what lets this report run on the host
    # that replicates, where only the public key exists.
    if [ -n "$newest" ]; then
        replica="$offsite/$(basename "$newest").gpg"

        if [ ! -f "$replica" ]; then
            bad "no off-site replica of the newest dump ($(basename "$newest").gpg)"
        elif [ ! -f "${replica}.json" ]; then
            bad "off-site replica manifest missing: $(basename "$replica").json"
        elif [ "$(read_sha256 "${replica}.json")" != "$(plain_checksum "$replica")" ]; then
            bad "off-site replica checksum mismatch: $(basename "$replica")"
        elif ! cistafirma_gpg_artifact_is_encrypted "$replica"; then
            # A file that is only *named* .gpg. The checksum above passed, so it
            # is exactly what the manifest describes -- and what it describes is
            # not ciphertext.
            bad "off-site replica is not an encrypted OpenPGP message: $(basename "$replica")"
        else
            replica_keyids=$(cistafirma_gpg_artifact_keyids "$replica" | paste -sd, -)
            configured_recipient=$(cistafirma_gpg_configured_recipient)

            if [ -n "$configured_recipient" ] && ! cistafirma_gpg_can_encrypt_to "$configured_recipient"; then
                # "Addressed to a key" is not the control. Without the public key
                # in this keyring the replica cannot be tied to the recipient
                # this machine believes in, and that is not a milder failure than
                # a missing replica -- it is the same one with the uncomfortable
                # detail that nobody actually looked.
                bad "the configured recipient '$configured_recipient' has no usable key in this keyring, so the replica cannot be shown to be encrypted to it (import it: make db-offsite-key-import PUBLIC_KEY_FILE=<file>)"
            elif [ -n "$configured_recipient" ] && ! cistafirma_gpg_artifact_matches_recipient "$replica" "$configured_recipient"; then
                bad "off-site replica is encrypted to $replica_keyids, which is not the configured recipient '$configured_recipient'"
            else
                ok "newest dump has a checksum-verified off-site replica, encrypted at source to $replica_keyids"
            fi
        fi
    fi

    # A replica written before the dump was encrypted at source is still sitting
    # there in the clear, and it is not a lesser finding than a missing replica:
    # it is the entire database readable by anyone who picks the disk up. It is
    # only detectable while the volume is attached, which is also the only moment
    # it can be removed -- so the fix is printed with the finding. prune is
    # dry-run unless --apply, so the operator sees the list before anything goes.
    plaintext_replicas=$(ls -1 "$offsite"/cistafirma_*.dump 2>/dev/null | LC_ALL=C sort || true)
    if [ -n "$plaintext_replicas" ]; then
        plaintext_count=$(printf '%s\n' "$plaintext_replicas" | wc -l | tr -d ' ')
        plaintext_names=$(printf '%s\n' "$plaintext_replicas" | xargs -n 1 basename | paste -sd, -)
        bad "off-site volume holds $plaintext_count unencrypted replica(s): $plaintext_names — the database is there in the clear. Remove them with: make db-backup-prune PRUNE_ARGS=\"--apply --offsite\""
    fi

    # --- destination volume encryption: context, not a gate --------------
    #
    # This verdict used to decide the gate. It cannot any more: what is written
    # off-host is ciphertext, so a volume that reports itself unencrypted -- or
    # one that cannot be asked at all -- cannot expose the database. The check
    # still runs and is still printed, because "we stopped looking" and "we
    # looked and it was fine" are different facts. Failing on it now would make
    # the gate report a control that no longer exists, and a gate that cries wolf
    # is the failure mode this whole report was built to avoid.
    mount_point=$(mount_point_of "$offsite")
    cistafirma_offsite_crypto_check "$offsite" "$mount_point"
    printf '  volume encryption: %s — %s\n' \
        "$CISTAFIRMA_OFFSITE_CRYPTO_VERDICT" "$CISTAFIRMA_OFFSITE_CRYPTO_REASON"
    printf '  %s\n' "(reported for context; the replica is encrypted at source and does not depend on it)"

    if cistafirma_offsite_crypto_override_active; then
        warn "CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP is still set and is no longer needed — the replica is encrypted before it is written; remove the line or set it to false"
    fi
fi

# --- restore drill -------------------------------------------------------
# A backup nobody has ever restored from is a hypothesis, not a control. The
# monthly cadence in docs/DATA_PROTECTION.md is only meaningful if a drill is
# recorded when it happens, so the gate reads the drill log back.
printf '\n'
drill_record=$(last_log_fields "$DRILL_LOG" timestamp backup public_tables source)

if [ -z "$drill_record" ]; then
    bad "no restore drill has been recorded in $DRILL_LOG"
else
    IFS=$'\t' read -r drill_time drill_backup drill_tables drill_source <<EOF
$drill_record
EOF
    days=$(iso_age_days "$drill_time")

    if [ "$days" -lt 0 ]; then
        bad "last recorded drill has an unreadable timestamp: $drill_time"
    else
        printf '  last drill       : %s (%s day(s) ago, %s, %s table(s))\n' \
            "${drill_backup:-unknown}" "$days" "${drill_source:-unknown}" "${drill_tables:-?}"
        if [ "$days" -gt "$MAX_DRILL_AGE_DAYS" ]; then
            bad "last restore drill was ${days} day(s) ago (limit ${MAX_DRILL_AGE_DAYS})"
        else
            ok "restore drill is recent (${days} day(s) ago)"
        fi

        # The doc asks for the monthly drill to come from the external copy once
        # one exists -- restoring the local dump does not prove the off-site one.
        # "Once one exists" means once the destination is really attached: a
        # directory that is present but unreachable has no off-site copy to
        # drill, and telling the operator to drill it would send them after a
        # volume that is not there.
        #
        # The second precondition is the host itself. The replica is encrypted
        # to the public key, so a host holding only that half can write and
        # verify replicas for ever and never read one -- which is the point of
        # encrypting at source, and also means the off-site drill is not this
        # host's to run. Warning anyway asks for something the machine cannot
        # do, and an unanswerable warning is how a report teaches its reader to
        # skip warnings. The drill belongs to the keyholder, so this says that
        # instead of counting it against the host.
        if [ "$drill_source" != "off-site" ] &&
            cistafirma_offsite_mount_check "${CISTAFIRMA_OFFSITE_BACKUP_DIR:-}" "$offsite_reference"; then
            if cistafirma_gpg_has_secret_key "$(cistafirma_gpg_configured_recipient)"; then
                warn "last drill used the local backup; drill the off-site copy when one is present"
            else
                printf '  off-site drill   : not runnable on this host — it holds only the public key, so it can write and verify replicas but never read one\n'
                printf '  %s\n' "(an encrypted replica has to be drilled where the private key is — see docs/DATA_PROTECTION.md)"
            fi
        fi
    fi
fi

# --- off-site replica staleness -----------------------------------------
# Read from a local record rather than from the volume. docs/DATA_PROTECTION.md
# says to keep the disk disconnected except while replicating, so its mtimes are
# unavailable exactly when this question matters most: "has it been attached
# lately?". The newest-replica check above answers "is the current dump safe?";
# this one answers "is the whole off-site habit still alive?", and only a local
# record can answer it while the disk is away.
printf '\n'
replica_record=$(last_log_fields "$REPLICA_LOG" timestamp backup)

if [ -z "$replica_record" ]; then
    bad "no off-site replica has ever been recorded in $REPLICA_LOG"
else
    IFS=$'\t' read -r replica_time replica_backup <<EOF
$replica_record
EOF
    days=$(iso_age_days "$replica_time")

    if [ "$days" -lt 0 ]; then
        bad "last recorded replica has an unreadable timestamp: $replica_time"
    else
        printf '  last replica     : %s (%s day(s) ago)\n' "${replica_backup:-unknown}" "$days"
        if [ "$days" -gt "$MAX_REPLICA_AGE_DAYS" ]; then
            bad "no off-site replica for ${days} day(s) (limit ${MAX_REPLICA_AGE_DAYS}) -- attach the volume and replicate"
        else
            ok "off-site replication is recent (${days} day(s) ago)"
        fi
    fi
fi

printf '\n'
# Both counts are published as their own summary lines, and they are the only
# thing a caller may read. The verdict below says whether the controls hold;
# this one says how much was excused, which the verdict cannot express -- a
# caller that counted the `WARN  ` lines instead would be coupled to this
# script's spacing through a convention neither script owns, and a control
# that silently under-reports is worse than one that reports nothing, because
# it is believed. Printed before the verdict, and on both exits, so the count
# is available whether or not the controls were satisfied.
echo "Off-site backup warnings: $warnings"

if [ "$failures" -eq 0 ]; then
    echo "Off-site backup controls: SATISFIED"
    exit 0
fi

echo "Off-site backup controls: $failures unmet" >&2
exit 1
