#!/usr/bin/env bash
set -Eeuo pipefail

LIB_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib

# Machine-local off-site configuration; an already exported
# CISTAFIRMA_OFFSITE_BACKUP_DIR wins over the config file. See lib/backup_env.sh.
# shellcheck source=lib/backup_env.sh
. "$LIB_DIR/backup_env.sh"
# Platform primitives (stat/checksum/mount-point/state dir) and the encryption
# verdict. Sourced after backup_env.sh so a machine-local CISTAFIRMA_* setting
# is in scope for both.
# shellcheck source=lib/backup_os.sh
. "$LIB_DIR/backup_os.sh"
# shellcheck source=lib/offsite_crypto.sh
. "$LIB_DIR/offsite_crypto.sh"
# shellcheck source=lib/backup_gpg.sh
. "$LIB_DIR/backup_gpg.sh"

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 /absolute/path/to/cistafirma_*.dump" >&2
    exit 64
fi

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
BACKUP_FILE=$(cd "$(dirname "$1")" && pwd -P)/$(basename "$1")
OFFSITE_DIR="${CISTAFIRMA_OFFSITE_BACKUP_DIR:-}"

# The recipient is resolved first, before the destination is even looked at.
# It is a configuration fact rather than a hardware state, and it is the one
# blocker an operator can act on without walking to the machine and plugging
# something in. More importantly, resolving it here is what guarantees that the
# plaintext path below is unreachable: there is no branch in this script that
# writes a dump off-host without encrypting it first.
RECIPIENT=$(cistafirma_gpg_require_recipient) || exit 1

if [ -z "$OFFSITE_DIR" ]; then
    echo "ERROR: CISTAFIRMA_OFFSITE_BACKUP_DIR is not set and no machine-local" >&2
    echo "       config supplied it. Record the volume once with:" >&2
    echo "         make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR=$(example_offsite_dir)" >&2
    echo "       or pass it for a single run: make db-backup-replicate BACKUP_FILE=... CISTAFIRMA_OFFSITE_BACKUP_DIR=..." >&2
    exit 1
fi

# "It is attached" is a fact about the kernel, not about the existence of a
# path. On Linux the off-site destination is typically an armed systemd
# automount, which keeps the directory -- and even a mountinfo entry -- present
# while its target is unreachable, so a test on the path alone would pass and
# the "replica" would be written onto the same disk as the original. See
# cistafirma_offsite_mount_check for what is actually measured.
if ! cistafirma_offsite_mount_check "$OFFSITE_DIR" "$(dirname "$BACKUP_FILE")"; then
    if [ "$CISTAFIRMA_OFFSITE_MOUNT_VERDICT" = "same-filesystem" ]; then
        echo "ERROR: off-site backup directory must be on a different filesystem." >&2
    else
        # Word for word what production has always printed.
        echo "ERROR: off-site backup directory is not mounted or does not exist: $OFFSITE_DIR" >&2
        # The reason is for the Linux host, where "the automount could not reach
        # its target" and "someone typed the wrong path" call for different
        # actions. macOS prints exactly the line it always has.
        if [ "$CISTAFIRMA_OS" != "macos" ]; then
            echo "       ${CISTAFIRMA_OFFSITE_MOUNT_REASON}" >&2
        fi
    fi
    exit 1
fi

OFFSITE_DIR=$(cd "$OFFSITE_DIR" && pwd -P)
# Kept from before the port. It re-asks a question the check above has already
# answered, once symlinks are resolved, and a mistake this expensive is worth
# refusing twice.
if [ "$(device_id_of "$(dirname "$BACKUP_FILE")")" = "$(device_id_of "$OFFSITE_DIR")" ]; then
    echo "ERROR: off-site backup directory must be on a different filesystem." >&2
    exit 1
fi

# The dump is verified before anything is written anywhere, so a corrupt source
# is refused rather than faithfully encrypted into a replica of a broken file.
"$ROOT_DIR/scripts/local/verify_postgres_backup.sh" "$BACKUP_FILE"

OFFSITE_BACKUP="${OFFSITE_DIR}/$(basename "$BACKUP_FILE").gpg"

# Encrypted at source: the ciphertext is produced here, from the local dump, and
# this is the only thing that is ever written to the off-site destination.
cistafirma_gpg_encrypt "$BACKUP_FILE" "$OFFSITE_BACKUP" "$RECIPIENT"

# The manifest describes the *artifact*, not the dump it came from: its checksum
# is the checksum of the ciphertext. A manifest carried over from the local dump
# would fail verification against the replica -- correctly, but the report would
# point at a corrupt copy rather than at a mismatched manifest.
#
# The key ids are recorded from the message itself rather than assumed from the
# recipient, so that a reader with no keyring at all can still check that the
# bytes on the disk are the bytes that were encrypted, and were addressed to the
# key this machine believes in.
ARTIFACT_KEYIDS=$(cistafirma_gpg_artifact_keyids "$OFFSITE_BACKUP" | paste -sd, -)
if [ -z "$ARTIFACT_KEYIDS" ]; then
    # cistafirma_gpg_encrypt already refused a non-encrypted output, so reaching
    # this line means gpg's own bookkeeping changed under us. Removing the
    # artifact rather than recording it is the only safe reading: an off-site
    # file whose encryption cannot be re-established must not be left looking
    # like a replica.
    rm -f -- "$OFFSITE_BACKUP"
    echo "ERROR: the replica's encryption could not be re-established; it was removed." >&2
    exit 1
fi

umask 077
REPLICA_MANIFEST="${OFFSITE_BACKUP}.json"
MANIFEST_TMP="${REPLICA_MANIFEST}.partial.$$"
trap 'rm -f -- "$MANIFEST_TMP"' EXIT

# The checksum is taken with the same helper the rest of the tooling uses, from
# the same place, so the digest in this manifest and the digest recomputed by
# offsite_status.sh can never come from two different implementations.
replica_sha=$(sha256_of "$OFFSITE_BACKUP")

python3 - "$OFFSITE_BACKUP" "$REPLICA_MANIFEST" "$MANIFEST_TMP" "$RECIPIENT" "$ARTIFACT_KEYIDS" "$BACKUP_FILE" "$replica_sha" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

replica, manifest, tmp, recipient, keyids, source, sha = sys.argv[1:8]
replica_path = Path(replica)
source_path = Path(source)

def read_sha(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))["sha256"]
    except Exception:
        return ""

data = {
    "format": "postgresql-custom",
    "encrypted": True,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "filename": replica_path.name,
    "sha256": sha,
    "size_bytes": replica_path.stat().st_size,
    "encryption": {
        "scheme": "openpgp-public-key",
        "recipient": recipient,
        "keyids": [k for k in keyids.split(",") if k],
    },
    # Provenance, so a replica can be traced back to the dump it was made from
    # without decrypting it -- which is the only way to ask that question on a
    # host that holds no private key.
    "source": {
        "filename": source_path.name,
        "sha256": read_sha(f"{source}.json"),
    },
}

Path(tmp).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
PY

mv -f -- "$MANIFEST_TMP" "$REPLICA_MANIFEST"
trap - EXIT

# Verified after it is in place, through the same entry point the scheduler and
# the gate use: the checksum must match the manifest, and the artifact must still
# be a public-key encrypted message carrying the key ids the manifest claims.
# Neither question needs the private key, which is the point -- the host that
# writes a replica is not the host that can read one.
"$ROOT_DIR/scripts/local/verify_postgres_backup.sh" "$OFFSITE_BACKUP"

# --- destination volume encryption: context, no longer a gate ---------------
#
# Before the replica was encrypted at source this verdict decided whether the
# copy happened. It no longer does, and the change is deliberate rather than a
# relaxation: what is written to the destination is ciphertext, so a volume that
# reports itself unencrypted -- or that cannot be asked at all -- cannot expose
# the database. The check still runs, because "we stopped looking" and "we looked
# and it is fine" are different facts, and only one of them is worth reporting.
#
# It is kept as a second, independent lock for the artifacts that predate this
# change: a plaintext replica written by an older version of this script is
# exactly what an encrypted volume still protects. offsite_status.sh fails on
# finding one, and prune --offsite removes it.
VOLUME_MOUNT_POINT=$(mount_point_of "$OFFSITE_DIR") || true
if [ -n "${VOLUME_MOUNT_POINT:-}" ]; then
    cistafirma_offsite_crypto_check "$OFFSITE_DIR" "$VOLUME_MOUNT_POINT"
else
    CISTAFIRMA_OFFSITE_CRYPTO_VERDICT="unknown"
    CISTAFIRMA_OFFSITE_CRYPTO_REASON="the off-site volume mount point could not be determined"
fi

echo "NOTE: destination volume encryption: $CISTAFIRMA_OFFSITE_CRYPTO_VERDICT — $CISTAFIRMA_OFFSITE_CRYPTO_REASON"
echo "NOTE: this does not gate the copy. The replica is encrypted at source, so what"
echo "      is stored off-host is ciphertext whether or not the volume is encrypted."

if cistafirma_offsite_crypto_override_active; then
    echo "WARNING: CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP is still set and is no" >&2
    echo "         longer needed: the replica is encrypted before it is written. Remove" >&2
    echo "         the line from your machine-local config, or set it to false." >&2
fi

# Record the replica. The volume is documented as normally disconnected, so the
# replica file's own mtime is unavailable exactly when the staleness question
# matters most -- "has the disk been attached lately?". A local record is the
# only thing that can answer that while the disk is away. Written only after
# both the source and the copy verified, so the record means a real replica.
REPLICA_LOG="${CISTAFIRMA_REPLICA_LOG:-$(state_dir)/replicas.log}"

umask 077
mkdir -p "$(dirname "$REPLICA_LOG")"
python3 - "$REPLICA_LOG" "$OFFSITE_BACKUP" "$replica_sha" "$OFFSITE_DIR" "$RECIPIENT" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

log_path, replica_path, sha, offsite_dir, recipient = sys.argv[1:6]
record = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "backup": Path(replica_path).name,
    "sha256": sha,
    "offsite_dir": offsite_dir,
    "recipient": recipient,
}
with open(log_path, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
PY

echo "Off-site replica verified (encrypted at source): $OFFSITE_BACKUP"
echo "  recipient : $RECIPIENT"
echo "  key ids   : $ARTIFACT_KEYIDS"
echo "Recorded in: $REPLICA_LOG"
