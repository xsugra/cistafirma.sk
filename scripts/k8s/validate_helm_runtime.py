#!/usr/bin/env python3
"""Fail CI when a rendered Helm release lacks required async runtime workloads.

Run with a rendered manifest to check it, or with `--selftest <manifest>` to
check the checker: that mode corrupts the manifest in memory the way the release
would have to be broken for the frontend check to matter, and requires the check
to reject it. A gate nobody has watched fail is a gate that might not be wired
to anything -- the lesson this repository keeps re-learning about `total_run_count`
and `grep -c`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

EXPECTED_QUEUES = {"ruz_full", "orsr", "financials", "insurance", "celery"}

# The name the frontend image has baked in as its default, and therefore the
# value that appears when nothing overrides it. It is the *kustomize* Service
# name, so in a Helm release it names nothing and every API request 502s.
STALE_UPSTREAM = "cistafirma-backend:8000"


class ContractError(Exception):
    """A rendered release that breaks the contract this script checks."""


def fail(message: str) -> None:
    raise ContractError(message)


def deployment_documents(rendered_manifest: str) -> list[str]:
    return [
        document
        for document in re.split(r"^---\s*$", rendered_manifest, flags=re.MULTILINE)
        if re.search(r"^kind:\s*Deployment\s*$", document, flags=re.MULTILINE)
    ]


def frontend_proxy_target(rendered_manifest: str, documents: list[str]) -> str:
    """Return the address the frontend proxies to, checking it names a real Service.

    This is the check the 2026-09-17 outage class asked for. The chart names the
    backend Service `<release>-cistafirma-backend`, while the frontend image had
    the *kustomize* name `cistafirma-backend` baked in as its default -- and the
    documented releases are `cistafirma-dev` / `cistafirma-prod`. The two names
    never met, and nothing noticed: nginx resolves the upstream at run time now,
    so a name that does not exist is a 502 per request rather than a refusal to
    start, and the frontend probe is blind to the backend by design. Comparing
    the rendered value against the Services in the same render catches it in CI.
    """
    upstreams = [
        match.group(1)
        for document in documents
        if re.search(
            r'app\.kubernetes\.io/component:\s*"?frontend"?\s*$',
            document,
            flags=re.MULTILINE,
        )
        for match in re.finditer(
            r'^\s*-\s*name:\s*BACKEND_UPSTREAM\s*\n\s*value:\s*"?([^"\n]+)"?\s*$',
            document,
            flags=re.MULTILINE,
        )
    ]
    if len(upstreams) != 1:
        fail(
            "Expected exactly one frontend Deployment env BACKEND_UPSTREAM, "
            f"found {len(upstreams)}. Without it nginx keeps the image default, "
            "which names the kustomize Service rather than this chart's."
        )

    upstream = upstreams[0].strip()
    host, _, port = upstream.partition(":")
    if not host or not port:
        fail(f"BACKEND_UPSTREAM '{upstream}' is not a host:port address.")

    service_names = {
        match.group(1)
        for document in re.split(r"^---\s*$", rendered_manifest, flags=re.MULTILINE)
        if re.search(r"^kind:\s*Service\s*$", document, flags=re.MULTILINE)
        for match in re.finditer(r"^\s*name:\s*([^\s#]+)\s*$", document, flags=re.MULTILINE)
    }
    if host not in service_names:
        fail(
            f"Frontend proxies to '{upstream}', but the rendered release has no "
            f"Service named '{host}'. Services present: "
            f"{', '.join(sorted(service_names)) or 'none'}. nginx resolves this "
            "name at run time, so this is not a start-up failure -- it is a 502 "
            "on every API request while the pod reports healthy."
        )

    return upstream


def check(rendered_manifest: str) -> str:
    """Validate one rendered release. Returns the frontend's proxy target."""
    deployments = deployment_documents(rendered_manifest)
    if not deployments:
        fail("Rendered manifest contains no Deployments.")

    components = set()
    worker_queues = set()
    beat_deployments = 0

    for deployment in deployments:
        component_match = re.search(
            r"^\s*app\.kubernetes\.io/component:\s*([^\s#]+)\s*$",
            deployment,
            flags=re.MULTILINE,
        )
        if component_match:
            components.add(component_match.group(1).strip('"'))

        queue_match = re.search(
            r'^\s*cistafirma\.sk/celery-queue:\s*"?([^"\s#]+)"?\s*$',
            deployment,
            flags=re.MULTILINE,
        )
        if queue_match:
            queue = queue_match.group(1)
            worker_queues.add(queue)
            if not re.search(
                rf"\bcelery\s+-A\s+backend\s+worker\b[\s\S]*?\s-Q\s+{re.escape(queue)}\b",
                deployment,
            ):
                fail(f"Celery worker for queue '{queue}' lacks the matching -Q command.")

        if re.search(r"\bcelery\s+-A\s+backend\s+beat\b", deployment):
            beat_deployments += 1

    missing_components = {"backend", "frontend"} - components
    if missing_components:
        fail(f"Missing required deployment components: {', '.join(sorted(missing_components))}.")

    if worker_queues != EXPECTED_QUEUES:
        missing_queues = EXPECTED_QUEUES - worker_queues
        unexpected_queues = worker_queues - EXPECTED_QUEUES
        details = []
        if missing_queues:
            details.append(f"missing {', '.join(sorted(missing_queues))}")
        if unexpected_queues:
            details.append(f"unexpected {', '.join(sorted(unexpected_queues))}")
        fail(f"Celery queue deployment contract mismatch ({'; '.join(details)}).")

    if beat_deployments != 1:
        fail(f"Expected exactly one Celery Beat deployment, found {beat_deployments}.")

    return frontend_proxy_target(rendered_manifest, deployments)


def selftest(rendered_manifest: str) -> None:
    """Require `check` to reject a release the frontend check exists to catch.

    Two states, because there are two ways this goes wrong: the upstream names a
    Service that is not in the release (the drift that was live in the chart),
    and the upstream is absent altogether (the image default quietly takes over).
    A third case -- two frontend containers disagreeing -- is not constructed
    here, since `replicaCount` cannot produce it.
    """
    replaced, count = re.subn(
        r'(^\s*-\s*name:\s*BACKEND_UPSTREAM\s*\n\s*value:\s*)"?[^"\n]+"?\s*$',
        rf'\g<1>"{STALE_UPSTREAM}"',
        rendered_manifest,
        flags=re.MULTILINE,
    )
    if count != 1:
        fail(f"Selftest could not rewrite BACKEND_UPSTREAM (matched {count} times).")

    cases = [
        ("a drifted upstream name", replaced),
        (
            "a missing BACKEND_UPSTREAM",
            re.sub(
                r"^\s*-\s*name:\s*BACKEND_UPSTREAM\s*\n\s*value:\s*\"?[^\"\n]+\"?\s*$\n",
                "",
                rendered_manifest,
                flags=re.MULTILINE,
            ),
        ),
    ]

    for description, broken in cases:
        try:
            check(broken)
        except ContractError:
            continue
        fail(f"Selftest failed: `check` accepted {description}.")

    print(
        "Self-test passed: the frontend check rejects a drifted upstream name "
        "and a missing one."
    )


def main() -> None:
    args = sys.argv[1:]
    self_test = bool(args) and args[0] == "--selftest"
    if self_test:
        args = args[1:]

    if len(args) != 1:
        fail(
            f"Usage: {Path(sys.argv[0]).name} [--selftest] /path/to/rendered-manifest.yaml"
        )

    manifest_path = Path(args[0])
    if not manifest_path.is_file():
        fail(f"Rendered manifest does not exist: {manifest_path}")

    rendered_manifest = manifest_path.read_text(encoding="utf-8")

    if self_test:
        try:
            selftest(rendered_manifest)
        except ContractError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            raise SystemExit(1)
        return

    try:
        upstream = check(rendered_manifest)
    except ContractError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)

    print(
        "Helm runtime contract valid: backend, frontend, one Celery Beat, "
        f"workers for {', '.join(sorted(EXPECTED_QUEUES))}, and a frontend "
        f"proxying to the rendered Service '{upstream}'."
    )


if __name__ == "__main__":
    main()
