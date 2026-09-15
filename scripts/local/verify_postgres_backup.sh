#!/usr/bin/env bash
set -Eeuo pipefail

# Only the platform primitives, not lib/backup_env.sh: this script reads no
# CISTAFIRMA_* setting, and reading the machine-local config here would give it
# a dependency on a file it has never needed. lib/backup_gpg.sh is different --
# it reads no configuration either, so the same property holds.
# shellcheck source=lib/backup_os.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/backup_os.sh"
# shellcheck source=lib/backup_gpg.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/backup_gpg.sh"

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 /absolute/path/to/cistafirma_*.dump[.gpg]" >&2
    exit 64
fi

BACKUP_FILE=$1

if [ ! -f "$BACKUP_FILE" ] || [ ! -s "$BACKUP_FILE" ]; then
    echo "ERROR: backup file does not exist or is empty: $BACKUP_FILE" >&2
    exit 1
fi

METADATA_FILE="${BACKUP_FILE}.json"
if [ ! -f "$METADATA_FILE" ]; then
    echo "ERROR: backup metadata is missing: $METADATA_FILE" >&2
    exit 1
fi

expected_checksum=$(python3 - "$METADATA_FILE" <<'PY'
import json
import sys
from pathlib import Path

metadata = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(metadata["sha256"])
PY
)
actual_checksum=$(sha256_of "$BACKUP_FILE")

if [ "$expected_checksum" != "$actual_checksum" ]; then
    echo "ERROR: checksum verification failed." >&2
    exit 1
fi

# Two kinds of artifact, two different questions, and the suffix decides which.
#
# A plaintext dump is verified by asking PostgreSQL to read it: pg_restore --list
# parses the archive, so a truncated or malformed dump fails here rather than at
# restore time. That check is the whole point of this script for a local backup.
#
# A .gpg replica cannot be verified that way on the host that writes it, and this
# is a property of the design rather than a limitation to work around: the
# replicating host holds only the public key and genuinely cannot decrypt. What
# it *can* establish without a private key is that the bytes are intact (the
# checksum above, against the manifest written beside it) and that they are still
# an OpenPGP message encrypted to the key ids the manifest claims. That is the
# question worth asking here -- "is this the artifact we think it is?" -- and it
# needs no keyring at all. Whether it *decrypts* is what the restore drill
# answers, on the machine that holds the private key.
case "$BACKUP_FILE" in
    *.gpg)
        if ! cistafirma_gpg_available; then
            echo "ERROR: gpg is not installed, so the encrypted replica cannot be inspected." >&2
            exit 1
        fi

        # Sorted and de-duplicated on both sides before the comparison, so the
        # check is about *which* keys the message is addressed to and not about
        # the order gpg happened to emit its packets in.
        if ! actual_keyids=$(cistafirma_gpg_artifact_keyids "$BACKUP_FILE" | LC_ALL=C sort -u); then
            echo "ERROR: $(basename "$BACKUP_FILE") is not a public-key encrypted OpenPGP message." >&2
            echo "       A file that is only *named* .gpg protects nothing. The checksum" >&2
            echo "       above passed, so what is on disk is what the manifest describes —" >&2
            echo "       and what it describes is not ciphertext." >&2
            exit 1
        fi

        recorded_keyids=$(python3 - "$METADATA_FILE" <<'PY'
import json
import sys
from pathlib import Path

metadata = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
keyids = (metadata.get("encryption") or {}).get("keyids") or []
print("\n".join(sorted(set(keyids))))
PY
)

        if [ -z "$recorded_keyids" ]; then
            echo "ERROR: $(basename "$METADATA_FILE") records no recipient key ids, so the" >&2
            echo "       encryption of the replica cannot be checked against it." >&2
            exit 1
        fi

        if [ "$actual_keyids" != "$recorded_keyids" ]; then            echo "ERROR: the replica is encrypted to different keys than its manifest claims." >&2
            echo "       manifest: $(printf '%s' "$recorded_keyids" | paste -sd, -)" >&2
            echo "       artifact: $(printf '%s' "$actual_keyids" | paste -sd, -)" >&2
            exit 1
        fi

        echo "Backup verified: $BACKUP_FILE (encrypted to $(printf '%s' "$actual_keyids" | paste -sd, -))"
        ;;
    *)
        docker image inspect postgres:16-alpine >/dev/null
        docker run --rm --pull=never \
            --mount "type=bind,source=$(cd "$(dirname "$BACKUP_FILE")" && pwd -P)/$(basename "$BACKUP_FILE"),target=/backup/input.dump,readonly" \
            postgres:16-alpine \
            pg_restore --list /backup/input.dump >/dev/null

        echo "Backup verified: $BACKUP_FILE"
        ;;
esac
