#!/usr/bin/env bash
# OpenPGP encryption of the off-site replica. Sourced, never executed.
#
# The replica that leaves this machine is encrypted *before* it is written, so
# "is the destination volume encrypted?" stops being the control and becomes
# context. What the control judges is the artifact -- and an artifact is a thing
# several scripts have to agree about: the one that writes it, the one that
# verifies it, the one that reports on it, the one that prunes it and the one
# that restores it. So the encryption lives here once, exactly as the volume
# verdict lives in lib/offsite_crypto.sh once, and for the same reason: the
# script that writes a replica and the report that is believed must never
# disagree.
#
# The one rule this file exists to enforce:
#
#     A missing, unusable or failing key NEVER produces a plaintext replica.
#
# Encryption that silently falls back to plaintext on error is worse than no
# encryption at all, because it looks finished. Every failure below returns
# non-zero and leaves no destination file behind, and the caller is expected to
# stop rather than continue.
#
# No configuration is read here beyond the recipient itself, so a machine that
# only *inspects* an artifact (verify_postgres_backup.sh) can source this file
# without also sourcing lib/backup_env.sh.

# Overridable so a test can drive a scratch keyring; the default is the user's.
CISTAFIRMA_GPG_BIN="${CISTAFIRMA_GPG_BIN:-gpg}"

cistafirma_gpg_available() {
    command -v "$CISTAFIRMA_GPG_BIN" >/dev/null 2>&1
}

# The recipient is machine-local configuration, in the same file as the off-site
# path itself (~/.config/cistafirma/backup.env), because it differs per machine:
# the host that replicates needs the *public* key, the machine that runs a
# recovery drill needs the private one.
cistafirma_gpg_configured_recipient() {
    printf '%s' "${CISTAFIRMA_OFFSITE_GPG_RECIPIENT:-}"
}

# Can this keyring actually encrypt to that recipient? Naming a recipient is not
# the same as holding a usable key for it: a fingerprint that was never imported,
# or a key with no encryption-capable (sub)key, both look configured and then
# fail at the first real backup -- which is the worst possible moment.
cistafirma_gpg_can_encrypt_to() {
    local recipient="$1"

    cistafirma_gpg_available || return 1
    [ -n "$recipient" ] || return 1

    "$CISTAFIRMA_GPG_BIN" --batch --with-colons --list-keys -- "$recipient" 2>/dev/null |
        awk -F: '/^(pub|sub):/ && $12 ~ /e/ { found = 1 } END { exit !found }'
}

# Every long key id that can be the encryption target of a message addressed to
# this recipient. The encryption subkey is the usual answer -- an ed25519
# sign-only primary key cannot encrypt at all -- so both are printed and the
# caller accepts either. See cistafirma_gpg_artifact_keyids for the other side of
# the comparison.
cistafirma_gpg_keyids_for() {
    local recipient="$1"

    "$CISTAFIRMA_GPG_BIN" --batch --with-colons --list-keys -- "$recipient" 2>/dev/null |
        awk -F: '/^(pub|sub):/ && $12 ~ /e/ { print $5 }'
}

# The key ids a message is actually encrypted to. Read from the message itself,
# with `--list-packets`, which needs NO private key and not even a keyring --
# that is what makes it usable on the host that replicates, where only the public
# key exists, and on a host that has neither.
#
# Returns 1 with no output when the file is not a public-key encrypted OpenPGP
# message. That is not a cosmetic difference: a file that is merely *named* .gpg
# protects nothing, and this is the only place that can tell the two apart
# without a private key.
cistafirma_gpg_artifact_keyids() {
    local file="$1"
    local keyids

    cistafirma_gpg_available || return 1
    [ -f "$file" ] || return 1

    keyids=$("$CISTAFIRMA_GPG_BIN" --batch --list-packets -- "$file" 2>/dev/null |
        awk '/^:pubkey enc packet:/ { for (i = 1; i <= NF; i++) if ($i == "keyid") print $(i + 1) }')

    [ -n "$keyids" ] || return 1
    printf '%s\n' "$keyids"
}

# Is this artifact a public-key encrypted message? A predicate, for the callers
# that only need the yes/no and word the failure themselves.
cistafirma_gpg_artifact_is_encrypted() {
    cistafirma_gpg_artifact_keyids "$1" >/dev/null 2>&1
}

# Is the artifact encrypted to *this* recipient -- every key it is addressed to
# belonging to that key, and at least one of them?
#
# "Addressed to some key" is not the control. The failure this exists to catch is
# a replica encrypted to a key nobody has any more, or to a key that is not the
# one this machine believes in: both look exactly like a working replica from the
# outside, and both are discovered at restore time. Returns non-zero when it
# cannot be established as well as when it is false -- a keyring without the
# public key cannot answer the question, and "could not check" must not read as
# "checked, and it was fine".
cistafirma_gpg_artifact_matches_recipient() {
    local file="$1"
    local recipient="$2"
    local artifact_keyids expected keyid

    cistafirma_gpg_can_encrypt_to "$recipient" || return 1
    artifact_keyids=$(cistafirma_gpg_artifact_keyids "$file") || return 1
    expected=$(cistafirma_gpg_keyids_for "$recipient" || true)

    while IFS= read -r keyid; do
        [ -n "$keyid" ] || continue
        printf '%s\n' "$expected" | grep -qxF -- "$keyid" || return 1
    done <<< "$artifact_keyids"

    return 0
}

# Print the configured recipient, or explain why replication cannot proceed and
# return non-zero. The message lives here so every caller gives the same one:
# this is the point at which an operator learns that the feature exists, and a
# second, differently-worded copy of it would teach them something else.
cistafirma_gpg_require_recipient() {
    local recipient

    if ! cistafirma_gpg_available; then
        echo "ERROR: gpg is not installed, so the replica cannot be encrypted at source." >&2
        echo "       Install it (apt install gnupg / brew install gnupg), or the off-site copy cannot be made." >&2
        return 1
    fi

    recipient=$(cistafirma_gpg_configured_recipient)
    if [ -z "$recipient" ]; then
        cat >&2 <<'MSG'
ERROR: no OpenPGP recipient is configured, so the off-site replica cannot be
       encrypted at source -- and an unencrypted replica is never written.

       Record it once (the public key of the backup keypair):

         make db-offsite-key-status                       # what is set up here
         make db-offsite-key-export                       # write the public key out
         make db-offsite-configure CISTAFIRMA_OFFSITE_BACKUP_DIR="<dir>" \
              CISTAFIRMA_OFFSITE_GPG_RECIPIENT="<fingerprint or key id>"

       The private half of that keypair is needed only to restore; see
       docs/DATA_PROTECTION.md, "External encrypted replica".
MSG
        return 1
    fi

    if ! cistafirma_gpg_can_encrypt_to "$recipient"; then
        echo "ERROR: no usable encryption key for '$recipient' is in this keyring," >&2
        echo "       so the replica cannot be encrypted and will not be written." >&2
        echo "       Import the public key (make db-offsite-key-import PUBLIC_KEY_FILE=<file>)," >&2
        echo "       or correct CISTAFIRMA_OFFSITE_GPG_RECIPIENT if the fingerprint is wrong." >&2
        return 1
    fi

    printf '%s' "$recipient"
}

# Usage: cistafirma_gpg_encrypt <source> <destination> [<recipient>]
#
# Writes the ciphertext to a temporary name beside the destination and renames it
# into place only after the result has been checked. Two failure modes are being
# closed at once: a gpg that dies halfway must not leave a file that a later
# `[ -f ]` or a partial-transfer retry reads as a finished replica, and a gpg
# that exits 0 without producing an encrypted message must not be trusted on its
# exit code alone. The rename is atomic within the destination's filesystem, so
# the artifact either does not exist or is complete.
cistafirma_gpg_encrypt() {
    local src="$1"
    local dst="$2"
    local recipient="${3:-}"
    local tmp="${dst}.partial.$$"

    [ -f "$src" ] || {
        echo "ERROR: nothing to encrypt: $src does not exist." >&2
        return 1
    }

    if [ -z "$recipient" ]; then
        recipient=$(cistafirma_gpg_require_recipient) || return 1
    fi

    umask 077
    rm -f -- "$tmp"

    # --trust-model always is deliberate. The operator names the recipient in the
    # machine-local configuration; that act IS the trust decision, and it is a
    # better one than a web-of-trust path. Without it an unattended weekly job
    # fails on "There is no assurance this key belongs to the named user" -- a
    # failure about gpg's bookkeeping, not about the backup, arriving at 3am with
    # nobody in front of it.
    if ! "$CISTAFIRMA_GPG_BIN" --batch --yes --no-tty --trust-model always \
        --output "$tmp" --encrypt --recipient "$recipient" -- "$src"; then
        rm -f -- "$tmp"
        echo "ERROR: gpg failed to encrypt the dump. No replica was written." >&2
        return 1
    fi

    if [ ! -s "$tmp" ]; then
        rm -f -- "$tmp"
        echo "ERROR: gpg produced an empty file. No replica was written." >&2
        return 1
    fi

    if ! cistafirma_gpg_artifact_is_encrypted "$tmp"; then
        rm -f -- "$tmp"
        echo "ERROR: the file gpg produced is not a public-key encrypted message." >&2
        echo "       Refusing to install it as a replica. No replica was written." >&2
        return 1
    fi

    mv -f -- "$tmp" "$dst"
}

# Usage: cistafirma_gpg_decrypt <source> <destination>
#
# Deliberately NOT --batch: this runs on a machine where the private key lives,
# and a passphrase-protected key must be able to reach a pinentry prompt. An
# unattended caller does not exist for this direction -- nothing decrypts a
# backup on a schedule.
cistafirma_gpg_decrypt() {
    local src="$1"
    local dst="$2"

    if ! cistafirma_gpg_available; then
        echo "ERROR: gpg is not installed, so $src cannot be decrypted." >&2
        return 1
    fi

    umask 077
    if ! "$CISTAFIRMA_GPG_BIN" --yes --output "$dst" --decrypt -- "$src"; then
        rm -f -- "$dst"
        cat >&2 <<MSG
ERROR: could not decrypt $src.

       Two causes, and they need different fixes:

         * the private key is not in this keyring -- a machine that only holds
           the public key can write and verify replicas but can never read one.
           Recovery therefore has to run where the private key is.
         * the key is here but its passphrase could not be asked for -- run this
           from a terminal, so pinentry can prompt.
MSG
        return 1
    fi

    if [ ! -s "$dst" ]; then
        rm -f -- "$dst"
        echo "ERROR: decrypting $src produced an empty file." >&2
        return 1
    fi
}
