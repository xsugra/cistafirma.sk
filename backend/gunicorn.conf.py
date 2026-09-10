"""Gunicorn configuration.

The only job here is prometheus_client multiprocess hygiene.

With more than one worker every worker is a separate process holding its own
in-process counters, so a scrape returns whichever worker happened to answer:
the exported series oscillates (3, 3, 5, 3 ...) and Prometheus reads the drops
as counter resets, which makes rate() meaningless. PROMETHEUS_MULTIPROC_DIR
moves the counter values into memory-mapped files shared by all workers, and
core/metrics.py aggregates them at scrape time with MultiProcessCollector.

The directory must start empty. Files are named after the worker pid, so files
left by a previous run keep contributing their frozen values forever. The wipe
happens in on_starting -- in the master, before any worker forks -- so no
worker can ever delete another worker's files.

Files of workers that exit mid-run are deliberately NOT removed: keeping the
frozen values is what makes the exported totals monotonic, which is what
Prometheus requires.
"""

from __future__ import annotations

import os
import shutil


def on_starting(server):  # noqa: ARG001 — gunicorn hook signature
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not multiproc_dir:
        return

    os.makedirs(multiproc_dir, exist_ok=True)
    for entry in os.listdir(multiproc_dir):
        path = os.path.join(multiproc_dir, entry)
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except OSError:
            # Already gone (or not ours) — nothing to clean up.
            pass
