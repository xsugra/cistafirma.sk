#!/usr/bin/env bash
# "Is the off-site backup destination encrypted?" -- asked once, answered per
# platform. Sourced, never executed.
#
# Two scripts need this verdict: replicate_postgres_backup.sh, which is about to
# copy a database dump there, and offsite_status.sh, which reports on it. They
# must never disagree -- the one that copies is the one that matters and the one
# that reports is the one that is believed -- so the question is implemented
# here once rather than in each of them.
#
# The result is published as two variables rather than as a return code, because
# the two callers word the outcome differently and both are correct: one aborts
# a copy with an ERROR, the other prints a FAIL line in a report.
#
#   CISTAFIRMA_OFFSITE_CRYPTO_VERDICT = encrypted | unencrypted | unknown
#   CISTAFIRMA_OFFSITE_CRYPTO_REASON  = one line saying why, and what was looked at
#
# `unknown` is NOT a synonym for `unencrypted`, and callers must not collapse
# them: it means the check could not be carried out at all. It fails exactly
# like `unencrypted` does -- with the same override token, so an operator never
# has to learn a second one -- but it says so, because a control that cannot
# distinguish "verified safe" from "verified nothing" is the defect class this
# repository keeps re-learning.
#
# Requires lib/backup_os.sh to have been sourced first (CISTAFIRMA_OS).

# The one escape hatch, unchanged since before the port: an operator who has
# explicitly accepted an unverified destination. Read here rather than in each
# caller so that "the override" cannot come to mean two different things.
cistafirma_offsite_crypto_override_active() {
    [ "${CISTAFIRMA_ALLOW_UNENCRYPTED_OFFSITE_BACKUP:-false}" = "true" ]
}

cistafirma_crypto_verdict_encrypted() {
    CISTAFIRMA_OFFSITE_CRYPTO_VERDICT="encrypted"
    CISTAFIRMA_OFFSITE_CRYPTO_REASON="$1"
}

cistafirma_crypto_verdict_unencrypted() {
    CISTAFIRMA_OFFSITE_CRYPTO_VERDICT="unencrypted"
    CISTAFIRMA_OFFSITE_CRYPTO_REASON="$1"
}

cistafirma_crypto_verdict_unknown() {
    CISTAFIRMA_OFFSITE_CRYPTO_VERDICT="unknown"
    CISTAFIRMA_OFFSITE_CRYPTO_REASON="$1"
}

# Usage: cistafirma_offsite_crypto_check <offsite_dir> [<mount_point>]
#
# The mount point is passed in because replicate_postgres_backup.sh has to
# reject an undeterminable one *before* any encryption question is asked, with
# its own error message; the macOS branch is the branch that needs the value.
# The Linux branch re-derives everything it needs from the directory.
cistafirma_offsite_crypto_check() {
    local dir="$1"
    local mount_point="${2:-}"

    CISTAFIRMA_OFFSITE_CRYPTO_VERDICT="unknown"
    CISTAFIRMA_OFFSITE_CRYPTO_REASON="no encryption check was run"

    case "$CISTAFIRMA_OS" in
        macos) cistafirma_crypto_check_macos "$mount_point" ;;
        linux) cistafirma_crypto_check_linux "$dir" ;;
        *)
            cistafirma_crypto_verdict_unknown \
                "no encryption check exists for platform '$CISTAFIRMA_OS'"
            ;;
    esac
}

# --- macOS -----------------------------------------------------------------
#
# Unchanged from the macOS-only tooling, failure mode included: a `diskutil`
# that cannot answer -- no such device, an empty or unreadable mount point --
# is reported as *unencrypted*, exactly as before. That is a deliberate refusal
# to relax the production platform while the migration is still running. On
# macOS `diskutil` is always present, so "could not answer" only ever meant
# "this is not a volume that reports itself as encrypted".
cistafirma_crypto_check_macos() {
    local mount_point="$1"

    if diskutil info "$mount_point" 2>/dev/null | grep -Eq 'FileVault:.*Yes|Encrypted:.*Yes'; then
        cistafirma_crypto_verdict_encrypted \
            "diskutil reports the volume at $mount_point as encrypted"
    else
        cistafirma_crypto_verdict_unencrypted \
            "diskutil does not report the volume at ${mount_point:-<undetermined>} as encrypted"
    fi
}

# --- Linux -----------------------------------------------------------------
#
# Three cases, and they are three different questions:
#
#   (a) the off-site directory is on a local block device
#       -> that device, or something below it, must be dm-crypt/LUKS.
#   (b) the off-site directory is a FUSE mount -- in practice sshfs to the
#       off-site host
#       -> nothing on *this* machine can answer it, because the bytes are not
#          stored here. The question is asked on the far side, over SSH.
#   (c) anything else -- NFS, CIFS, tmpfs, an overlay
#       -> FAIL. Not because those are necessarily unsafe, but because this
#          tooling has no verified way to tell whether they are, and a check
#          that guesses is worse than one that admits it did not run.
cistafirma_crypto_check_linux() {
    local dir="$1"
    local fstype source

    if ! command -v findmnt >/dev/null 2>&1; then
        cistafirma_crypto_verdict_unknown \
            "findmnt is not installed, so the filesystem holding $dir cannot be identified"
        return 0
    fi

    fstype=$(findmnt -no FSTYPE --target "$dir" 2>/dev/null || true)
    if [ -z "$fstype" ]; then
        cistafirma_crypto_verdict_unknown \
            "findmnt could not determine the filesystem type of $dir"
        return 0
    fi

    case "$fstype" in
        fuse*)
            cistafirma_crypto_check_linux_fuse "$dir" "$fstype"
            return 0
            ;;
    esac

    source=$(findmnt -no SOURCE --target "$dir" 2>/dev/null || true)
    case "$source" in
        /dev/*)
            cistafirma_crypto_check_linux_block "$source"
            ;;
        *)
            cistafirma_crypto_verdict_unknown \
                "case (c): $dir is on '$source' (fstype '$fstype'), which is neither a local block device nor a FUSE mount, and this tooling cannot verify encryption on it"
            ;;
    esac
}

# Case (a): is the block device behind the directory encrypted?
#
# Two questions, because one is not enough. `cryptsetup status` answers directly
# for a device-mapper target, which is what an opened LUKS container is -- but
# an LVM logical volume stacked on a LUKS container is not itself a crypt
# target, and that layout must still be called encrypted. `lsblk -s` walks the
# device's *parents* on the other hand, so it finds the LUKS layer wherever in
# the stack it sits: `part crypto_LUKS` under a `crypt` mapper under an `lvm`
# volume all appear in one listing. A positive answer from either is enough; if
# neither tool could answer, the verdict is unknown rather than unencrypted,
# because "I could not look" and "I looked and it is plaintext" are different
# facts and only one of them is the operator's fault.
cistafirma_crypto_check_linux_block() {
    local source="$1"
    local tree saw_tool=false

    if command -v cryptsetup >/dev/null 2>&1; then
        saw_tool=true
        if cryptsetup status "$source" >/dev/null 2>&1; then
            cistafirma_crypto_verdict_encrypted \
                "cryptsetup reports $source as a dm-crypt mapping"
            return 0
        fi
    fi

    if command -v lsblk >/dev/null 2>&1; then
        saw_tool=true
        tree=$(lsblk -s -no TYPE,FSTYPE "$source" 2>/dev/null || true)
        if [ -n "$tree" ]; then
            if printf '%s\n' "$tree" | grep -Eq '(^|[[:space:]])crypt([[:space:]]|$)|crypto_LUKS'; then
                cistafirma_crypto_verdict_encrypted \
                    "$source sits above a dm-crypt/LUKS layer: $(printf '%s' "$tree" | tr '\n' ' ')"
            else
                cistafirma_crypto_verdict_unencrypted \
                    "$source has no dm-crypt/LUKS layer in its stack: $(printf '%s' "$tree" | tr '\n' ' ')"
            fi
            return 0
        fi
    fi

    if [ "$saw_tool" = false ]; then
        cistafirma_crypto_verdict_unknown \
            "neither lsblk nor cryptsetup is installed, so $source cannot be examined"
    else
        cistafirma_crypto_verdict_unknown \
            "lsblk could not describe $source, so its encryption cannot be established"
    fi
}

# Case (b): FUSE, in practice sshfs.
#
# The bytes are on the far side, so the far side is asked. Two things have to be
# derived: which host, and which path on it.
#
#   * the host and path come from the mount itself -- sshfs's mount source is
#     literally `user@host:/remote/path` -- or, when an operator has pinned
#     them, from CISTAFIRMA_OFFSITE_SSH_TARGET (same `user@host:/path` form),
#     which also covers mounts whose source does not carry an address.
#   * `ssh` is given BatchMode and a connect timeout. A check that can block on
#     a password prompt is a check that never reaches a verdict, and a control
#     that never returns is the failure mode this repository already documents
#     as its worst one. An unanswered question is `unknown`, which fails.
#
# The remote program is the same local-block-device question, run where the
# device lives. The path travels base64-encoded inside the heredoc: it is the
# only quoting that survives both the local shell, ssh's own argument joining
# (which does not quote) and whatever `sh` the remote host runs.
cistafirma_crypto_check_linux_fuse() {
    local dir="$1"
    local fstype="$2"
    local source target host path path_b64 output last verdict reason

    source=$(findmnt -no SOURCE --target "$dir" 2>/dev/null || true)
    target="${CISTAFIRMA_OFFSITE_SSH_TARGET:-$source}"

    case "$target" in
        *:*) ;;
        *)
            cistafirma_crypto_verdict_unknown \
                "case (b): $dir is a $fstype mount but its remote target could not be derived from '$target'; set CISTAFIRMA_OFFSITE_SSH_TARGET=user@host:/path to have it checked over SSH"
            return 0
            ;;
    esac

    host=${target%%:*}
    path=${target#*:}

    if [ -z "$host" ] || [ -z "$path" ]; then
        cistafirma_crypto_verdict_unknown \
            "case (b): $dir is a $fstype mount but its remote target '$target' is incomplete"
        return 0
    fi

    if ! command -v ssh >/dev/null 2>&1; then
        cistafirma_crypto_verdict_unknown \
            "case (b): $dir is a $fstype mount on $host, and ssh is not installed here, so the remote volume cannot be checked"
        return 0
    fi

    if ! command -v base64 >/dev/null 2>&1; then
        cistafirma_crypto_verdict_unknown \
            "case (b): $dir is a $fstype mount on $host, and base64 is not installed here, so the remote path cannot be passed safely"
        return 0
    fi

    path_b64=$(printf '%s' "$path" | base64 | tr -d '\n')

    output=$(ssh -o BatchMode=yes -o ConnectTimeout=10 -- "$host" sh -s <<REMOTE 2>/dev/null || true
target=\$(printf '%s' '$path_b64' | base64 -d)
if [ ! -d "\$target" ]; then
    echo "unknown the off-site directory does not exist on the remote host"
    exit 0
fi
if ! command -v findmnt >/dev/null 2>&1; then
    echo "unknown findmnt is not installed on the remote host"
    exit 0
fi
source=\$(findmnt -no SOURCE --target "\$target" 2>/dev/null || true)
fstype=\$(findmnt -no FSTYPE --target "\$target" 2>/dev/null || true)
case "\$source" in
    /dev/*) ;;
    *)
        echo "unknown the remote directory is not on a block device (source '\$source', fstype '\$fstype')"
        exit 0
        ;;
esac
if ! command -v lsblk >/dev/null 2>&1; then
    echo "unknown lsblk is not installed on the remote host"
    exit 0
fi
tree=\$(lsblk -s -no TYPE,FSTYPE "\$source" 2>/dev/null || true)
if [ -z "\$tree" ]; then
    echo "unknown lsblk could not describe \$source on the remote host"
    exit 0
fi
if printf '%s\n' "\$tree" | grep -Eq '(^|[[:space:]])crypt([[:space:]]|\$)|crypto_LUKS'; then
    echo "encrypted the remote device \$source is dm-crypt/LUKS"
else
    echo "unencrypted the remote device \$source has no dm-crypt/LUKS layer above it"
fi
REMOTE
)

    # A login banner, an ssh warning or a shell hook may prepend lines to the
    # remote session's stdout. Only the last line is this check's answer, and it
    # is accepted only if its first word is one of the two verdicts -- anything
    # else is not a verdict, and is reported as unknown rather than read as one.
    last=$(printf '%s' "$output" | awk 'NF { line = $0 } END { print line }')
    verdict=${last%% *}
    reason=${last#* }

    case "$verdict" in
        encrypted)
            cistafirma_crypto_verdict_encrypted "case (b): $reason (checked over ssh on $host)"
            ;;
        unencrypted)
            cistafirma_crypto_verdict_unencrypted "case (b): $reason (checked over ssh on $host)"
            ;;
        *)
            cistafirma_crypto_verdict_unknown \
                "case (b): $dir is a $fstype mount on $host, and the remote check did not answer -- ssh must work unattended for this user (BatchMode, no password prompt) and the host key must already be known"
            ;;
    esac
}
