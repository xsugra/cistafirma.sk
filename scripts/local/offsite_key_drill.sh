#!/usr/bin/env bash
# Prove that an exported private key can actually READ an off-site replica.
#
# The restore drill answers "is this backup restorable?". This answers a
# different question, and it is the one that stops having an answer the moment
# the key is lost: "would I still be able to restore if the machine holding the
# key were gone?". So the object under test is not this machine's keyring but
# an *exported* copy of the key -- ideally the one kept in the password
# manager, because that is the thing a person would actually reach for after a
# disk died.
#
# It is a separate command because the obvious check is not sufficient. An
# export can contain exactly one private key block, import cleanly, and carry a
# fingerprint matching the expected key -- and still be unable to decrypt
# anything, if the cv25519 encryption subkey is missing. All three of those
# look perfect, and the failure surfaces at restore time, which is the worst
# possible moment to find out. The only thing that settles it is a decryption,
# so this runs a real one: the key goes into an EMPTY keyring and the replica
# is restored using nothing else.
#
# What it never touches: this machine's own keyring (nothing is imported into
# it), and the running database. The restore goes through
# restore_postgres_drill.sh, which always targets an isolated container.
#
# Run it from a terminal, not from CI or another agent: decryption reaches the
# private key through gpg-agent, which needs a tty for pinentry. Without one it
# fails with "Inappropriate ioctl for device", which reads like a key problem
# and is not one.
set -Eeuo pipefail

LIB_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib
# shellcheck source=lib/backup_env.sh
. "$LIB_DIR/backup_env.sh"
# shellcheck source=lib/backup_os.sh
. "$LIB_DIR/backup_os.sh"
# shellcheck source=lib/backup_gpg.sh
. "$LIB_DIR/backup_gpg.sh"

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
DRILL_SCRIPT="$ROOT_DIR/scripts/local/restore_postgres_drill.sh"

# The exported secret key to test. Taken from the environment so that `make`
# can pass it without this script having to re-implement make's conditionals,
# and accepted as a flag for direct use.
KEY_FILE="${CISTAFIRMA_KEY_DRILL_KEY_FILE:-}"

usage() {
    cat <<'USAGE'
Usage: offsite_key_drill.sh [--key-file <exported-secret-key>] [<replica.dump.gpg>]

  --key-file FILE   the exported secret key to test. Point this at the copy
                    kept in the password manager: the point of the command is
                    to test the object you would really reach for, not the
                    keyring you happen to be sitting in front of. When it is
                    omitted a fresh export is taken from the local keyring,
                    which proves the export format is complete but says
                    nothing about whether any copy was ever stored.

  <replica>         the encrypted replica to restore. Defaults to the newest
                    *.dump.gpg in the configured off-site directory.

Exits non-zero when the key cannot restore the replica. A successful run is
recorded in the restore drill log like any other drill, because it is one.

See docs/DATA_PROTECTION.md, "External encrypted replica".
USAGE
}

# Mirrors the flag parsing of restore_postgres_drill.sh: a bare path is what
# people type, and `make` forwards one too.
while [ $# -gt 0 ]; do
    case "$1" in
        --key-file)
            KEY_FILE="${2:-}"
            [ -n "$KEY_FILE" ] || { echo "ERROR: --key-file needs a file" >&2; exit 64; }
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            echo "ERROR: unknown option: $1" >&2
            usage >&2
            exit 64
            ;;
        *)
            break
            ;;
    esac
done

replica="${1:-}"

if [ -z "$replica" ]; then
    # Same source of truth as every other off-site script: the machine-local
    # config, overridable by an exported variable.
    offsite="${CISTAFIRMA_OFFSITE_BACKUP_DIR:-}"
    if [ -n "$offsite" ] && [ -d "$offsite" ]; then
        replica=$(ls -1 "$offsite"/cistafirma_*.dump.gpg 2>/dev/null | LC_ALL=C sort | tail -n 1 || true)
    fi
fi

if [ -z "$replica" ]; then
    echo "ERROR: no replica to drill. Pass one, or configure the off-site directory:" >&2
    echo "       make db-offsite-key-drill BACKUP_FILE=<replica.dump.gpg>" >&2
    exit 64
fi

if [ ! -f "$replica" ]; then
    echo "ERROR: replica not found: $replica" >&2
    exit 1
fi

replica=$(cd "$(dirname "$replica")" && pwd -P)/$(basename "$replica")

if ! cistafirma_gpg_available; then
    echo "ERROR: gpg is not installed, so no replica can be decrypted here." >&2
    exit 1
fi

# A file that is only *named* .gpg would otherwise be discovered by the
# decryption step, as a confusing gpg error rather than as this sentence.
if ! cistafirma_gpg_artifact_is_encrypted "$replica"; then
    echo "ERROR: not an encrypted OpenPGP message: $replica" >&2
    echo "       Refusing to treat a plain rename as a replica." >&2
    exit 1
fi

TMP_HOME=$(mktemp -d)
chmod 700 "$TMP_HOME"
# The export lives beside the keyring it is imported into, so one trap removes
# both -- an exported private key left on disk is exactly the object this whole
# design keeps off the replicating hosts.
EXPORTED="$TMP_HOME/exported-secret-key.asc"
cleanup() { rm -rf "$TMP_HOME"; }
trap cleanup EXIT

echo "Off-site key drill"
echo "  replica    : $(basename "$replica")"
echo "  keyring    : a scratch one, thrown away at the end"
echo

if [ -n "$KEY_FILE" ]; then
    if [ ! -f "$KEY_FILE" ]; then
        echo "ERROR: key file not found: $KEY_FILE" >&2
        exit 1
    fi
    echo "Reading the exported key (this is the copy from the password manager):"
    source_file="$KEY_FILE"
else
    recipient=$(cistafirma_gpg_configured_recipient)
    if [ -z "$recipient" ]; then
        echo "ERROR: nothing to test. Pass --key-file, or configure a recipient so a" >&2
        echo "       fresh export can be taken: make db-offsite-key-status" >&2
        exit 1
    fi
    echo "No --key-file given, so exporting a fresh copy from this machine's keyring."
    echo "This proves the export is complete; it does NOT prove that any copy was"
    echo "stored anywhere. For that, pass the password-manager copy as --key-file."
    echo
    if ! "$CISTAFIRMA_GPG_BIN" --batch --yes --armor --output "$EXPORTED" \
        --export-secret-keys -- "$recipient"; then
        echo "ERROR: exporting the private key failed." >&2
        echo "       If gpg mentioned the agent or /dev/tty, run this from a terminal." >&2
        exit 1
    fi
    source_file="$EXPORTED"
fi

private_blocks=$(grep -c 'BEGIN PGP PRIVATE KEY BLOCK' "$source_file" 2>/dev/null || true)
if [ "${private_blocks:-0}" = "0" ]; then
    echo "ERROR: $source_file contains no private key block." >&2
    echo "       This is the public key, or not a key at all. Without the private" >&2
    echo "       half it can verify a replica for ever and never read one." >&2
    exit 1
fi

echo
echo "Importing into the scratch keyring (this machine's own keyring is untouched)..."
if ! "$CISTAFIRMA_GPG_BIN" --homedir "$TMP_HOME" --batch --import "$source_file"; then
    echo "ERROR: importing the key failed." >&2
    exit 1
fi

# The check that catches the expensive mistake. A key without an
# encryption-capable secret subkey imports perfectly and cannot decrypt
# anything; failing here names the problem while it is still cheap to fix.
secret_encryption_subkeys=$("$CISTAFIRMA_GPG_BIN" --homedir "$TMP_HOME" --batch \
    --with-colons --list-secret-keys 2>/dev/null |
    awk -F: '/^ssb:/ && $12 ~ /e/ { print $5 }')
secret_primaries=$("$CISTAFIRMA_GPG_BIN" --homedir "$TMP_HOME" --batch \
    --with-colons --list-secret-keys 2>/dev/null |
    awk -F: '/^sec:/ { print $5 }')

echo
echo "  secret primary key : ${secret_primaries:-<none>}"
echo "  encrypt subkey     : ${secret_encryption_subkeys:-<none>}"

if [ -z "$secret_primaries" ]; then
    echo
    echo "ERROR: the key did not import as a usable private key." >&2
    exit 1
fi

if [ -z "$secret_encryption_subkeys" ]; then
    echo
    echo "ERROR: this key has no encryption-capable secret subkey, so it can never" >&2
    echo "       decrypt a replica. That is the failure this command exists to catch," >&2
    echo "       and it is invisible to a fingerprint comparison." >&2
    exit 1
fi

echo
echo "Restoring the replica with nothing but that key..."
echo
# GNUPGHOME is what makes the point: during this call gpg can see only the
# scratch keyring, so a restore that succeeds cannot have been helped by the
# real one.
GNUPGHOME="$TMP_HOME" "$DRILL_SCRIPT" "$replica"
status=$?

echo
if [ "$status" -eq 0 ]; then
    echo "Key drill passed: an exported copy of the key restored an encrypted off-site replica."
    echo "This is the only check that proves a stored copy would still be usable — it can"
    echo "only be run while the key exists, which is why it belongs on a schedule."
else
    echo "Key drill FAILED (exit $status)." >&2
    echo "The replica was not restored from the exported key. Do not treat the off-site" >&2
    echo "copy as recoverable until this passes." >&2
fi
exit "$status"
