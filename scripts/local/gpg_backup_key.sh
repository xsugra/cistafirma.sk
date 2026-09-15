#!/usr/bin/env bash
# The backup keypair: create it, move its public half to the host that
# replicates, and answer "will replication work on this machine?".
#
# The off-site replica is encrypted to a key, so the key is part of the backup
# story and not a detail of it. The direction of travel is one-way and worth
# stating plainly, because getting it backwards is the mistake that costs the
# most:
#
#   * the PUBLIC key goes to every host that *writes* a replica (the server);
#   * the PRIVATE key stays where a *restore* would be run, plus an offline copy
#     in a password manager. A host that holds only the public key can write and
#     verify replicas, and can never read one.
#
# This is why `db-offsite-key-status` reports the private key's presence as its
# own line rather than folding it into "the key is fine": on the replicating host
# its absence is correct, and on the recovery host it is the whole problem.
set -Eeuo pipefail

LIB_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib
# shellcheck source=lib/backup_env.sh
. "$LIB_DIR/backup_env.sh"
# shellcheck source=lib/backup_os.sh
. "$LIB_DIR/backup_os.sh"
# shellcheck source=lib/backup_gpg.sh
. "$LIB_DIR/backup_gpg.sh"

DEFAULT_IDENTITY="CistaFirma backup <cistafirma-backup@localhost>"

usage() {
    cat <<'USAGE'
Usage: gpg_backup_key.sh <command> [argument]

  generate [identity]   create the backup keypair (asks for a passphrase)
  export [file]         write the public key out, for the host that replicates
  import <file>         import a public key written by `export`
  status                what is set up on this machine, and what is missing

The identity defaults to: CistaFirma backup <cistafirma-backup@localhost>

`export` writes to <state dir>/gpg/cistafirma-backup-public.asc when no file is
given. See docs/DATA_PROTECTION.md, "External encrypted replica".
USAGE
}

# Which key this machine's tooling means when it says "the backup key": the
# configured recipient when there is one, the default identity otherwise. On the
# host that replicates the recipient is what matters; on a host where the key is
# being created or exported it usually is not configured yet.
key_selector() {
    local configured
    configured=$(cistafirma_gpg_configured_recipient)
    if [ -n "$configured" ]; then
        printf '%s' "$configured"
    else
        printf '%s' "$DEFAULT_IDENTITY"
    fi
}

# The `|| true` on the gpg half of each pipeline is load-bearing. Under
# `set -o pipefail` a gpg that finds no matching key exits 2, and the assignment
# `x=$(fingerprints_of ...)` would then abort the whole script under `set -e` --
# so "this machine has no key" would be reported as a bare exit code instead of
# as the sentence that explains it, which is the one case the operator is most
# likely to be in.
fingerprints_of() {
    { "$CISTAFIRMA_GPG_BIN" --batch --with-colons --fingerprint --list-keys -- "$1" 2>/dev/null || true; } |
        awk -F: '/^fpr:/ { print $10 }'
}

encryption_subkeys_of() {
    { "$CISTAFIRMA_GPG_BIN" --batch --with-colons --list-keys -- "$1" 2>/dev/null || true; } |
        awk -F: '/^sub:/ && $12 ~ /e/ { print $5 }'
}

has_secret_key() {
    # Its own exit code is the answer, so this one keeps gpg's -- and is only
    # ever called from an `if`, where a non-zero status is a branch and not an
    # abort.
    "$CISTAFIRMA_GPG_BIN" --batch --with-colons --list-secret-keys -- "$1" 2>/dev/null |
        awk -F: '/^sec:/ { found = 1 } END { exit !found }'
}

need_gpg() {
    if ! cistafirma_gpg_available; then
        echo "ERROR: gpg is not installed." >&2
        exit 1
    fi
}

cmd_generate() {
    local identity="${1:-$DEFAULT_IDENTITY}"
    local existing

    need_gpg

    existing=$(fingerprints_of "$identity" | head -n 1)
    if [ -n "$existing" ]; then
        echo "A key for '$identity' already exists: $existing" >&2
        echo "Refusing to create a second one. Export it, or generate under a different identity." >&2
        exit 1
    fi

    # No --batch on purpose: gpg prompts for the passphrase through pinentry, so
    # it never appears in this script's arguments or in the process table. A
    # passphrase is asked for even though the drill is the only thing that needs
    # to type it -- the private key is the one object that can decrypt every
    # off-site backup, and it costs nothing at 3am to have it protected at rest.
    #
    # `default default never` is gpg's own recommended shape (an ed25519 signing
    # primary plus a cv25519 encryption subkey). It matters that the *subkey*
    # encrypts: a sign-only key reports "Unusable public key" the first time a
    # replica is attempted, which is a bad way to learn it.
    echo "Creating the backup keypair. gpg will ask for a passphrase —"
    echo "store it in the password manager next to the private key."
    echo

    if ! "$CISTAFIRMA_GPG_BIN" --quick-generate-key "$identity" default default never; then
        echo >&2
        echo "ERROR: key generation failed." >&2
        echo "       If gpg reported that it cannot open /dev/tty, run this from a" >&2
        echo "       terminal rather than from a script or a CI job." >&2
        exit 1
    fi

    local fingerprint
    fingerprint=$(fingerprints_of "$identity" | head -n 1)

    echo
    echo "Backup key created:"
    echo "  identity     : $identity"
    echo "  fingerprint  : $fingerprint"
    echo "  encrypts to  : $(encryption_subkeys_of "$identity" | paste -sd, -)"
    echo
    echo "Next, on every host that writes a replica (the server):"
    echo "  make db-offsite-key-export        # here"
    echo "  make db-offsite-key-import PUBLIC_KEY_FILE=<file>   # there"
    echo
    echo "Then record the recipient beside the off-site path:"
    echo "  make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR=\"<dir>\" \\"
    echo "       CISTAFIRMA_OFFSITE_GPG_RECIPIENT=\"$fingerprint\""
    echo
    echo "Keep the private key where a restore would be run, and an offline copy"
    echo "(exported secret key, or a paper backup of it) in the password manager."
}

cmd_export() {
    local selector target

    need_gpg
    selector=$(key_selector)

    target="${1:-$(state_dir)/gpg/cistafirma-backup-public.asc}"

    if [ -z "$(fingerprints_of "$selector" | head -n 1)" ]; then
        echo "ERROR: no key found for '$selector' on this machine." >&2
        echo "       Generate one first: make db-offsite-key-generate" >&2
        exit 1
    fi

    mkdir -p "$(dirname "$target")"
    umask 022 # a public key is public; it has to be readable by the account that imports it

    if ! "$CISTAFIRMA_GPG_BIN" --batch --armor --export -- "$selector" > "$target"; then
        rm -f -- "$target"
        echo "ERROR: exporting the public key failed." >&2
        exit 1
    fi

    echo "Public key written: $target"
    echo "  key         : $selector"
    echo "  fingerprint : $(fingerprints_of "$selector" | head -n 1)"
    echo
    echo "Copy it to the host that replicates, then there:"
    echo "  make db-offsite-key-import PUBLIC_KEY_FILE=$target"
}

cmd_import() {
    local file="${1:-}"

    need_gpg

    if [ -z "$file" ] || [ ! -f "$file" ]; then
        echo "Usage: $0 import <public-key-file>" >&2
        echo "ERROR: not a readable file: ${file:-<missing>}" >&2
        exit 64
    fi

    if ! "$CISTAFIRMA_GPG_BIN" --batch --import "$file"; then
        echo "ERROR: importing the public key failed." >&2
        exit 1
    fi

    echo
    echo "Imported. Verify the fingerprint against the machine that exported it"
    echo "before trusting it — the fingerprint is the only thing tying this key to"
    echo "that keypair:"
    echo
    cmd_status
}

cmd_status() {
    local selector configured recipient_info

    echo "CistaFirma backup key status"
    printf '  host             : %s\n' "$(hostname 2>/dev/null || echo unknown)"

    if ! cistafirma_gpg_available; then
        echo "  gpg              : NOT INSTALLED"
        echo
        echo "Replication and recovery both need gpg. Install it before continuing."
        exit 1
    fi
    printf '  gpg              : %s (%s)\n' \
        "$("$CISTAFIRMA_GPG_BIN" --version 2>/dev/null | head -n 1)" "$CISTAFIRMA_GPG_BIN"

    configured=$(cistafirma_gpg_configured_recipient)
    if [ -n "$configured" ]; then
        printf '  recipient        : %s\n' "$configured"
    else
        printf '  recipient        : <not set — replication cannot run here>\n'
    fi

    selector=$(key_selector)
    recipient_info=$(fingerprints_of "$selector" | head -n 1)

    if [ -z "$recipient_info" ]; then
        printf '  key in keyring   : NO — nothing matches %s\n' "$selector"
        echo
        echo "On a host that writes replicas: import the public key."
        echo "On the host that holds the keypair: create or restore it."
        exit 1
    fi

    printf '  key in keyring   : %s\n' "$recipient_info"
    printf '  encrypts to      : %s\n' "$(encryption_subkeys_of "$selector" | paste -sd, -)"

    if [ -z "$(encryption_subkeys_of "$selector")" ]; then
        printf '  usable for backup: NO — no encryption-capable subkey\n'
        echo
        echo "A signing-only key cannot encrypt. Recreate the keypair:"
        echo "  make db-offsite-key-generate"
        exit 1
    fi

    if has_secret_key "$selector"; then
        printf '  private key      : present — this host can restore an off-site replica\n'
    else
        printf '  private key      : absent — this host can write and verify replicas,\n'
        printf '                     but cannot read one. A recovery must run where the\n'
        printf '                     private key is.\n'
    fi

    echo
    if [ -n "$configured" ] && cistafirma_gpg_can_encrypt_to "$configured"; then
        echo "Replication is configured and can encrypt to the recorded recipient."
    elif [ -n "$configured" ]; then
        echo "The recorded recipient cannot be used — see the errors above."
        exit 1
    else
        echo "Record the recipient to enable replication:"
        echo "  make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR=\"<dir>\" \\"
        echo "       CISTAFIRMA_OFFSITE_GPG_RECIPIENT=\"$recipient_info\""
    fi
}

command="${1:-}"
shift || true

case "$command" in
    generate) cmd_generate "$@" ;;
    export) cmd_export "$@" ;;
    import) cmd_import "$@" ;;
    status) cmd_status ;;
    ''|-h|--help)
        usage
        [ -n "$command" ] || exit 64
        ;;
    *)
        echo "ERROR: unknown command: $command" >&2
        usage >&2
        exit 64
        ;;
esac
