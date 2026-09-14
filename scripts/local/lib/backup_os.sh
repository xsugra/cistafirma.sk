#!/usr/bin/env bash
# Platform portability layer. Sourced, never executed.
#
# This repository is moving from macOS (which is still production until the
# migration finishes) to Ubuntu Server, and the backup tooling is the part that
# has to survive the move intact. Every platform-dependent mechanism therefore
# lives *here* and nowhere else: a script that needs a `stat` flavour, a
# checksum tool, a mount-point resolver or a state directory asks this file for
# it instead of testing the platform itself.
#
# That single location is the point, not a style preference. A scattered
# `uname`-check is how a port quietly grows a second, subtly different opinion
# about which platform it is on -- and then the two branches stop being
# comparable, which is exactly the property that makes "macOS is unchanged"
# checkable at all.
#
# The macOS branches below reproduce, verbatim, what the macOS-only scripts did
# before this file existed -- same commands, same failure modes, same output
# text. Mac is still production, so porting may not tighten, relax or reword it.

# --- which platform is this ------------------------------------------------
#
# `uname -s` says `Darwin` on macOS and `Linux` on Linux. Anything else is
# `other`, and callers must treat `other` as unsupported rather than guess:
# guessing is how a control ends up verifying nothing on the platform it was
# never written for.
#
# CISTAFIRMA_OS_OVERRIDE is a *test* hook, not a configuration knob. It exists
# so the Linux branch can be exercised on the macOS machine that still holds the
# live data, without a second machine. It cannot loosen any control: forcing
# Linux on macOS lands in a branch whose tools (findmnt, lsblk, cryptsetup) are
# absent, and forcing macOS on Linux lands in one whose tool (diskutil) is
# absent -- both fail closed, and neither can report "encrypted" by accident.
# It is still announced whenever it changes the answer, because a run whose
# platform was forced is not a run whose verdict should be read without knowing
# that. Export it for a single run; do not record it anywhere.
cistafirma_detect_os() {
    local detected
    case "$(uname -s 2>/dev/null || true)" in
        Darwin) detected="macos" ;;
        Linux) detected="linux" ;;
        *) detected="other" ;;
    esac

    case "${CISTAFIRMA_OS_OVERRIDE:-}" in
        '') ;;
        macos | linux)
            if [ "$CISTAFIRMA_OS_OVERRIDE" != "$detected" ]; then
                printf 'WARNING: CISTAFIRMA_OS_OVERRIDE=%s forces the %s branch on a %s host (test hook only).\n' \
                    "$CISTAFIRMA_OS_OVERRIDE" "$CISTAFIRMA_OS_OVERRIDE" "$detected" >&2
            fi
            detected="$CISTAFIRMA_OS_OVERRIDE"
            ;;
        *)
            printf 'WARNING: ignoring CISTAFIRMA_OS_OVERRIDE=%s (expected macos or linux); using %s.\n' \
                "$CISTAFIRMA_OS_OVERRIDE" "$detected" >&2
            ;;
    esac

    printf '%s' "$detected"
}

CISTAFIRMA_OS=$(cistafirma_detect_os)

# --- primitives that differ between the two platforms ----------------------

# Device id of the filesystem holding a path, for "same filesystem?" tests.
# BSD `stat -f '%d'` is the macOS spelling, GNU `stat -c '%d'` is the Linux one,
# and neither accepts the other's flag. There is deliberately no `|| true` and
# no fallback chain between them: a wrong-flag call fails loudly and returns
# nothing, which a caller can detect, whereas a fallback that silently produced
# a device id from some other mechanism could make two filesystems look equal
# (or unequal) for a reason nobody wrote down.
device_id_of() {
    case "$CISTAFIRMA_OS" in
        macos) stat -f '%d' "$1" ;;
        linux) stat -c '%d' "$1" ;;
        *)
            echo "ERROR: device_id_of: no device-id check exists for platform '$CISTAFIRMA_OS'." >&2
            return 1
            ;;
    esac
}

# SHA-256 of a file, hex digest only.
#
# macOS ships `shasum` (the perl one) and not `sha256sum`; Linux ships
# `sha256sum` (coreutils) and does not guarantee perl. Each platform therefore
# gets the tool it actually guarantees rather than a fallback chain, so the
# checksum this project stores and verifies is produced by exactly one program
# per platform -- a "try this, then that" chain would mean a backup verified on
# one platform and checked on the other could have been hashed by two different
# implementations without anyone deciding that.
sha256_of() {
    case "$CISTAFIRMA_OS" in
        macos) shasum -a 256 "$1" | awk '{print $1}' ;;
        linux) sha256sum "$1" | awk '{print $1}' ;;
        *)
            echo "ERROR: sha256_of: no checksum tool is configured for platform '$CISTAFIRMA_OS'." >&2
            return 1
            ;;
    esac
}

# Mount point holding a path.
#
# macOS keeps the exact `df -P | awk` pipeline the scripts used before the port.
# Linux prefers `findmnt`, which reads /proc/self/mountinfo rather than stat()ing
# the mount and returns the mount point whole, where `df -P` splits on
# whitespace and would truncate a mount point containing a space. `df -P` stays
# as the fallback so that a host without util-linux does not turn "which
# filesystem is this" into a silent empty answer.
mount_point_of() {
    case "$CISTAFIRMA_OS" in
        macos) df -P "$1" | awk 'NR == 2 { print $NF }' ;;
        *)
            if command -v findmnt >/dev/null 2>&1; then
                findmnt -no TARGET --target "$1" 2>/dev/null || true
            else
                df -P "$1" | awk 'NR == 2 { print $NF }'
            fi
            ;;
    esac
}

# Directory holding durable per-user state: the backup directory, the drill log,
# the replica log.
#
# macOS keeps `~/Library/Application Support`, which is what the scripts
# hardcoded before the port. Linux uses the XDG state directory, which is where
# a Linux user's durable state belongs -- `~/Library/...` is not a path any
# Linux tool or operator would look in, and a backup directory nobody can find
# is only marginally better than no backup directory. XDG_STATE_HOME is honoured
# on both platforms, as it was before.
state_dir() {
    if [ "$CISTAFIRMA_OS" = "macos" ]; then
        printf '%s' "${XDG_STATE_HOME:-$HOME/Library/Application Support}/CistaFirma"
    else
        printf '%s' "${XDG_STATE_HOME:-$HOME/.local/state}/CistaFirma"
    fi
}

# Directory holding the unattended job's stdout/stderr.
#
# macOS keeps launchd's own files under ~/Library/Logs. On Linux the scheduler
# is systemd, which captures the unit's output in the journal as well; this
# directory is the file-based copy the status scripts and the gate read, because
# the journal is not persistent on every install and the controls must not
# depend on that.
log_dir() {
    if [ "$CISTAFIRMA_OS" = "macos" ]; then
        printf '%s' "$HOME/Library/Logs/CistaFirma"
    else
        printf '%s' "$(state_dir)/logs"
    fi
}

# Directory holding the per-user scheduler units, for the platform that has
# them. Printed by the installer so the operator can see what was written.
scheduler_unit_dir() {
    if [ "$CISTAFIRMA_OS" = "macos" ]; then
        printf '%s' "$HOME/Library/LaunchAgents"
    else
        printf '%s' "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
    fi
}

# An illustrative off-site path for help and error text.
#
# A helper rather than a literal in each message, because `/Volumes/...` is a
# macOS mount convention: the same hint shown on the Linux host would send an
# operator looking in a directory that cannot exist there. The macOS string is
# the exact one those messages have always printed.
example_offsite_dir() {
    if [ "$CISTAFIRMA_OS" = "macos" ]; then
        printf '%s' "/Volumes/<volume>/cistafirmaBackups"
    else
        printf '%s' "/mnt/<mount>/cistafirmaBackups"
    fi
}

# --- "is the off-site destination really attached?" ------------------------
#
# The single test for that question, used everywhere a script would otherwise
# write, prune, drill from or report on the off-site destination. Getting it
# wrong is not cosmetic: a destination that is *not* attached but whose path
# still exists is a plain directory on this machine's own disk, so a "replica"
# written there sits on the same disk as the original -- a second copy in name
# only, which is worse than no second copy because it is believed.
#
# Nothing that merely *describes* mounts can answer this. Measured on the Linux
# host (2026-09-15) with the destination configured as a systemd automount
# (`x-systemd.automount` in fstab over sshfs) and its target unreachable -- the
# normal state of a tailnet that is down:
#
#     [ -d /mnt/cistafirma-offsite ]        -> TRUE     (says nothing)
#     mountpoint -q /mnt/cistafirma-offsite -> MOUNTED  (WRONG)
#     findmnt -M /mnt/cistafirma-offsite    -> MOUNTED  (WRONG)
#     findmnt -t fuse.sshfs                 -> empty    (right, but says nothing
#                                                       about this destination)
#     stat -c '%d' /mnt/cistafirma-offsite  -> "No such device (os error 19)"
#     df -P /mnt/cistafirma-offsite         -> fails with ENODEV
#     the mount unit                        -> Active: failed
#
# `mountpoint` and `findmnt -M` are wrong here for a reason worth writing down,
# because it is the reverse of the usual advice: an armed automount keeps a
# mountinfo entry for the *trigger* itself for as long as the unit is armed,
# whether or not the filesystem behind it ever came up --
#
#     1656 48 0:80 / /mnt/cistafirma-offsite rw,relatime shared:564
#          - autofs systemd-1 rw,fd=100,...,direct,pipe_ino=175774
#
# so both tools faithfully report a mount that is not there. This is why the
# test below is not a mount-table inspection at all.
#
# The test performs a real filesystem operation and judges its *outcome*. `stat`
# is the discriminator: the kernel resolves the path, and when the automount
# cannot reach its target it fails with ENODEV rather than inventing an answer.
# Three facts, in order, none sufficient alone:
#
#   1. the path exists (`[ -d ]`) -- the only fact `[ -d ]` can establish, kept
#      because it rules out a plain typo cheaply and is what makes the reason
#      text useful;
#   2. `stat` on it succeeds. This is the test. ENODEV, a stalled sshfs, a
#      permission problem: every failure means "not attached", because in all of
#      them a write would either fail or land somewhere nobody chose. There is
#      deliberately no fallback and no `|| true` -- "could not determine" must
#      never be read as "attached";
#   3. its device id differs from a local reference (by default $HOME; callers
#      that know it pass the local backup directory instead). Without this, a
#      path that exists on this machine's own disk reads as "attached" -- which
#      on Linux is exactly what the automount's own directory is, and on macOS
#      is what a stale `/Volumes/<name>` directory left behind by an unclean
#      unmount is: the volume is gone, the directory is not, and a replica
#      written there lands on the internal SSD next to the original.
#
# That third fact is reported as its own verdict (`same-filesystem`), not folded
# into "not attached": it is a different mistake with a different fix, and the
# callers already have a precise message for it.
#
# `df -P` is deliberately NOT consulted here, although every caller does run it
# a few lines later. It reaches into the filesystem -- the very thing that is
# unreachable in the case above -- so it is at best a second opinion, and a
# second opinion is what it stays: no caller may treat a non-empty `df` mount
# point as the proof.
#
# The verdict is published in variables rather than echoed, because callers need
# to say *which* refusal happened. Callers must not invoke this inside `$( )`,
# which would discard them.
#
# CISTAFIRMA_OFFSITE_MOUNT_VERDICT = attached | same-filesystem | not-attached
# CISTAFIRMA_OFFSITE_MOUNT_REASON  = one line saying what was looked at
cistafirma_offsite_mount_check() {
    local dir="$1"
    local reference="${2:-}"
    local dir_dev ref ref_dev

    CISTAFIRMA_OFFSITE_MOUNT_REASON=""

    if [ ! -d "$dir" ]; then
        CISTAFIRMA_OFFSITE_MOUNT_VERDICT="not-attached"
        CISTAFIRMA_OFFSITE_MOUNT_REASON="$dir is not a directory"
        return 1
    fi

    if ! dir_dev=$(device_id_of "$dir" 2>/dev/null); then
        CISTAFIRMA_OFFSITE_MOUNT_VERDICT="not-attached"
        CISTAFIRMA_OFFSITE_MOUNT_REASON="the kernel would not resolve $dir (this is what an armed but unreachable automount reports: ENODEV)"
        return 1
    fi
    if [ -z "$dir_dev" ]; then
        CISTAFIRMA_OFFSITE_MOUNT_VERDICT="not-attached"
        CISTAFIRMA_OFFSITE_MOUNT_REASON="no device id could be read for $dir"
        return 1
    fi

    ref="${reference:-$HOME}"
    if ! ref_dev=$(device_id_of "$ref" 2>/dev/null); then
        ref_dev=""
    fi
    if [ -z "$ref_dev" ]; then
        # Without a reference the "different filesystem" fact cannot be shown,
        # and an unshowable fact is a refusal -- the alternative is calling a
        # path attached on the strength of a comparison that never happened.
        CISTAFIRMA_OFFSITE_MOUNT_VERDICT="not-attached"
        CISTAFIRMA_OFFSITE_MOUNT_REASON="$dir could not be compared with $ref, whose device id is unreadable"
        return 1
    fi

    if [ "$dir_dev" = "$ref_dev" ]; then
        CISTAFIRMA_OFFSITE_MOUNT_VERDICT="same-filesystem"
        CISTAFIRMA_OFFSITE_MOUNT_REASON="$dir is on this machine's own filesystem (device $dir_dev, the same as $ref)"
        return 1
    fi

    CISTAFIRMA_OFFSITE_MOUNT_VERDICT="attached"
    CISTAFIRMA_OFFSITE_MOUNT_REASON="$dir is on device $dir_dev, separate from $ref (device $ref_dev)"
    return 0
}

# True when the last cistafirma_offsite_mount_check established a usable,
# separate off-site filesystem. The reading the callers branch on.
cistafirma_offsite_mount_ok() {
    [ "${CISTAFIRMA_OFFSITE_MOUNT_VERDICT:-}" = "attached" ]
}
