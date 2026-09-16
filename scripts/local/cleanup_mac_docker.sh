#!/usr/bin/env bash
# Reclaim disk on the Mac from Docker images and build cache that nothing uses.
#
# The Mac is a development machine only (CLAUDE.md): it has no GitLab runner
# since 2026-09-15, its compose stack is a stopped frozen fallback, and CI runs
# on lenovo. What is left here are images pulled by jobs, tools and experiments
# that no longer exist. This script removes exactly those.
#
# Dry-run unless --apply is given. It deletes ONLY images, and only by explicit
# tag, plus the build cache. It never issues a volume command of any kind --
# `cistafirma_postgres_data` is attached to no container on this host, so a
# prune would destroy it, and docs/PLAN.md section 8 forbids that outright. The
# script asserts the volume still exists before and after, as a tripwire: no
# command here can remove a volume, so if it disappears the script did something
# it does not claim to do.
#
# Why an explicit tag list rather than `docker image prune -a`: prune keys off
# whether a *docker container* uses an image, and this host hides the Docker
# Desktop Kubernetes (kind) cluster -- its 6 nodes and every pod are invisible to
# `docker ps -a`. `prune -a` would therefore delete `kindest/node:*` (the images
# the cluster's nodes are made of), the cistafirma images the live deployments
# roll back to, and every k8s system image. Naming the tags is the whole point.
#
# Two classes of image LOOK unused by `docker ps -a` and must still survive:
#
#   1. Rollback targets. `scripts/k8s/rollback.sh` runs `kubectl rollout undo`,
#      which resolves the previous ReplicaSet's image by name. The registry that
#      served them (`localhost:5050`, the Mac GitLab) is gone, so the local store
#      holds the only copy. Every image named in any ReplicaSet is live, whether
#      or not a pod is running it.
#   2. Images of another project. `localhost:5050/web/code-reviews/*` belongs to
#      a container named `review-bot`, not to cistafirma.
#
# Both are computed at run time below, so this list does not rot when the
# cluster changes. Images referenced by `~/gitlab/docker-compose.yml`
# (`gitlab/gitlab-ee:nightly`, `gitlab/gitlab-runner:latest`) are kept by hand
# and explained at the list itself.
set -Eeuo pipefail

APPLY=false
for arg in "$@"; do
    case "$arg" in
        --apply) APPLY=true ;;
        -h | --help)
            sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg (try --help)" >&2
            exit 2
            ;;
    esac
done

CANARY_VOLUME=cistafirma_postgres_data

# Images to remove, by explicit tag. Each is either a pull from a job or tool
# that this repo no longer has (the `build`/`deploy`/`helm_k8s_validate` stages
# were deleted 2026-09-15; the Mac runner on 2026-09-15), or a moving tag
# superseded by a pinned one. All are public and re-pullable except
# bitnami/kubectl, which is dead upstream (Bitnami moved free images to
# `bitnamilegacy`) -- nothing uses it, so the loss is harmless.
DELETE_TAGS=(
    # Superseded by the pinned tags docker-compose.yml actually runs
    # (grafana/grafana:13.2.1, prom/prometheus:v3.14.0).
    grafana/grafana:latest
    prom/prometheus:latest
    prom/node-exporter:latest

    # The Mac GitLab whose container is gone. `:nightly` is NOT here: it is the
    # tag ~/gitlab/docker-compose.yml pins, next to a 1.6 GB data directory.
    gitlab/gitlab-ee:latest

    # GitLab CI security/scanning images -- the jobs that used them were removed
    # with the `build` stage, and CI now runs on lenovo.
    registry.gitlab.com/security-products/container-scanning:8
    registry.gitlab.com/security-products/semgrep:6
    registry.gitlab.com/security-products/secrets:7
    registry.gitlab.com/gitlab-org/cluster-integration/auto-build-image:v4.19.0
    registry.gitlab.com/gitlab-org/gitlab-runner/gitlab-runner-helper:arm64-v18.10.1
    registry.gitlab.com/gitlab-org/gitlab-runner/gitlab-runner-helper:arm64-v18.11.2

    # Docker-in-Docker. Build jobs need `privileged`, which the lenovo runner
    # deliberately refuses, so these can never run anywhere.
    docker:29.1.4
    docker:29.1.4-dind
    docker:27.1.2
    docker:27.1.2-dind
    docker:27.1.2-cli

    # The kubectl image of the deleted `helm_k8s_validate` job. It does not
    # exist upstream any more.
    bitnami/kubectl:1.30
    bitnami/kubectl:latest

    # Orphaned pulls and Docker Desktop's tutorial image.
    gliderlabs/herokuish:latest
    envoyproxy/envoy:v1.36.7
    envoyproxy/envoy:v1.36.4
    gcr.io/cadvisor/cadvisor:latest
    ghcr.io/jkroepke/kube-webhook-certgen:1.8.3
    docker/welcome-to-docker:latest
)

# Deliberately NOT in the list, and why:
#   kindest/node:*, docker/desktop-*   the live kind cluster and Docker Desktop
#   localhost:5050/web/cistafirma/*    rollback targets of live deployments
#   localhost:5050/web/code-reviews/*  another project (container `review-bot`)
#   cistafirma-*                       the frozen fallback compose stack
#   gitlab/gitlab-ee:nightly           pinned by ~/gitlab/docker-compose.yml
#   gitlab/gitlab-runner:latest        pinned by the same file
#   postgres:16-alpine, redis:7-alpine live in pods and in the compose stack
#   alpine*, python:3.12-slim, node:20-alpine, alpine/helm:3.17.2
#                                      the current CI job images -- small, and
#                                      they let a CI job be reproduced locally

hr() { printf '%s\n' "------------------------------------------------------------"; }

canary() {
    docker volume inspect "$CANARY_VOLUME" >/dev/null 2>&1
}

if ! canary; then
    echo "ERROR: volume '$CANARY_VOLUME' is missing BEFORE any deletion." >&2
    echo "       That is not this script's doing -- investigate before running." >&2
    exit 1
fi

# The set of images that a container uses, and that any pod or ReplicaSet names.
# A target found in here is skipped rather than deleted: the lists above are
# computed from the world as it is now, and this is what makes a stale entry in
# DELETE_TAGS harmless instead of destructive.
live_images() {
    docker ps -a --format '{{.Image}}'
    docker ps -a --format '{{.ImageID}}'
    if command -v kubectl >/dev/null 2>&1; then
        kubectl get pods,rs -A -o jsonpath='{range .items[*]}{range .spec.template.spec.containers[*]}{.image}{"\n"}{end}{range .spec.containers[*]}{.image}{"\n"}{end}{range .spec.initContainers[*]}{.image}{"\n"}{end}{end}' 2>/dev/null || true
    fi
}

echo "Docker images on the Mac, before:"
docker system df
hr

echo "Live images (used by a container, a pod or a ReplicaSet):"
LIVE="$(live_images | sed '/^$/d' | sort -u)"
printf '%s\n' "$LIVE" | sed 's/^/  /'
hr

resolvable=()
skipped=()
for tag in "${DELETE_TAGS[@]}"; do
    id="$(docker image inspect --format '{{.Id}}' "$tag" 2>/dev/null || true)"
    if [ -z "$id" ]; then
        # `docker images` and `docker image inspect` disagree about some tags on
        # this Docker Desktop (containerd image store): a tag is listed but
        # cannot be inspected or removed. Say which case it is -- reporting
        # "not present" for a tag the user can see in `docker images` is the
        # kind of misleading reason this repo treats as a defect.
        if docker images --format '{{.Repository}}:{{.Tag}}' | grep -Fxq "$tag"; then
            skipped+=("$tag (listed but not inspectable -- containerd store quirk)")
        else
            skipped+=("$tag (not present)")
        fi
        continue
    fi
    if printf '%s\n' "$LIVE" | grep -Fxq "$tag" || printf '%s\n' "$LIVE" | grep -Fxq "$id"; then
        skipped+=("$tag (LIVE -- refused)")
        continue
    fi
    resolvable+=("$tag")
done

if [ "${#skipped[@]}" -gt 0 ]; then
    echo "Skipped:"
    printf '  %s\n' "${skipped[@]}"
    hr
fi

echo "Build cache to reclaim:"
docker system df --format '{{.Type}}: {{.Reclaimable}} reclaimable' | grep -i cache || true
hr

if [ "${#resolvable[@]}" -eq 0 ]; then
    echo "Nothing to remove."
    exit 0
fi

echo "Would remove ${#resolvable[@]} images:"
printf '  %s\n' "${resolvable[@]}"

if [ "$APPLY" != true ]; then
    hr
    echo "Dry run -- nothing was deleted. Re-run with --apply to remove the above."
    echo "The build cache is pruned as well (docker builder prune -f); the next"
    echo "local image build will be slower and needs network access."
    exit 0
fi

hr
echo "Removing images..."
failed=0
for tag in "${resolvable[@]}"; do
    if ! docker rmi "$tag"; then
        echo "WARN: could not remove $tag (shared layers are fine; a real failure is not)" >&2
        failed=1
    fi
done

hr
echo "Pruning build cache..."
docker builder prune -f

hr
if ! canary; then
    echo "ERROR: volume '$CANARY_VOLUME' is GONE after the run." >&2
    echo "       Stop and investigate -- this script issues no volume command." >&2
    exit 1
fi
echo "OK: '$CANARY_VOLUME' is still present."

echo
echo "Docker images on the Mac, after:"
docker system df
hr
if [ "$failed" -ne 0 ]; then
    echo "Finished with warnings -- see WARN lines above."
    exit 1
fi
echo "Done."
