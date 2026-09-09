#!/usr/bin/env python3
"""Fail CI when a rendered Helm release lacks required async runtime workloads."""

from __future__ import annotations

import re
import sys
from pathlib import Path

EXPECTED_QUEUES = {"ruz_full", "orsr", "financials", "insurance", "celery"}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def deployment_documents(rendered_manifest: str) -> list[str]:
    return [
        document
        for document in re.split(r"^---\s*$", rendered_manifest, flags=re.MULTILINE)
        if re.search(r"^kind:\s*Deployment\s*$", document, flags=re.MULTILINE)
    ]


def main() -> None:
    if len(sys.argv) != 2:
        fail(f"Usage: {Path(sys.argv[0]).name} /path/to/rendered-manifest.yaml")

    manifest_path = Path(sys.argv[1])
    if not manifest_path.is_file():
        fail(f"Rendered manifest does not exist: {manifest_path}")

    deployments = deployment_documents(manifest_path.read_text(encoding="utf-8"))
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

    print(
        "Helm runtime contract valid: backend, frontend, one Celery Beat, "
        f"and workers for {', '.join(sorted(EXPECTED_QUEUES))}."
    )


if __name__ == "__main__":
    main()
