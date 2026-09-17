"""The one place that settles prometheus_client's multiprocess mode.

`prometheus_client` chooses between its two value classes exactly once, when
`prometheus_client.values` is first imported, and it chooses on the **presence**
of `PROMETHEUS_MULTIPROC_DIR` rather than on its value::

    # prometheus_client/values.py
    def get_value_class():
        if 'prometheus_multiproc_dir' in os.environ or 'PROMETHEUS_MULTIPROC_DIR' in os.environ:
            return MultiProcessValue()
        return MutexValue

    ValueClass = get_value_class()          # evaluated at import, once per process

Every reader in this repo -- `core/metrics.py`, `gunicorn.conf.py` -- reads the
same variable with `os.environ.get(...)`, and so treats an *empty* value as
unset. An empty-but-present variable is therefore the one input on which the
library and this repo disagree, and the disagreement is silent and expensive:

* the counters are memory-mapped through `os.path.join('', 'counter_1.db')`,
  which is a **relative** path -- i.e. into the process's working directory,
  which in this stack is the bind-mounted `/app`;
* the exporter still aggregates the default registry, so the files are written
  by nothing that is ever read.

Measured 2026-09-15: `docker compose run -e PROMETHEUS_MULTIPROC_DIR= backend
python manage.py shell` left root-owned `counter_1.db` and `histogram_1.db`
inside the production checkout on dell.

The other half of the same variable is that a *configured* directory which does
not exist is fatal rather than degrading. `MultiProcessCollector` raises
`ValueError: env PROMETHEUS_MULTIPROC_DIR is not set or not a directory`, and
even before that the first `Counter(...)` tries to memory-map a file in it and
raises `FileNotFoundError` -- so a missing directory does not cost `/metrics`,
it kills the process at import. That is not a hypothetical: it is what
`docker compose run backend ...` does, because the one-shot inherits the
variable from the service definition (docker-compose.yml sets it on `backend`
alone) and never runs gunicorn, which is the only thing that creates the
directory.

Both halves are settled here, once, from `settings.py`. That placement is not
cosmetic: Django imports settings before any app module, and the first metric in
the process is built at import time by `companies.models`
(`UNKNOWN_LEGAL_FORM_CODE_COUNT`), so a normalisation performed anywhere later
-- `core/metrics.py` itself included, since it is reached through `ROOT_URLCONF`
-- would already be too late. Once `ValueClass` is bound, nothing can rebind it.
"""

from __future__ import annotations

import os


def normalize_multiproc_env(environ=None) -> str | None:
    """Drop `PROMETHEUS_MULTIPROC_DIR` when it is set to nothing.

    Returns the directory left in force, or `None` when multiprocess mode is
    off. A value that is empty or only whitespace is removed from the
    environment entirely, so the presence test in `prometheus_client` and the
    truthiness test used everywhere in this repo cannot disagree. A value with
    surrounding whitespace is trimmed in place, because the library would
    otherwise use the padded string as a path.

    `environ` exists so this is testable without touching the real environment;
    callers pass nothing, and the mutation is the point.
    """
    if environ is None:
        environ = os.environ

    raw = environ.get("PROMETHEUS_MULTIPROC_DIR")
    if raw is None:
        return None

    value = raw.strip()
    if not value:
        environ.pop("PROMETHEUS_MULTIPROC_DIR", None)
        return None

    environ["PROMETHEUS_MULTIPROC_DIR"] = value
    return value


def ensure_multiproc_dir(path: str) -> str:
    """Create the multiprocess directory if it is missing, and return it.

    Only ever creates, never removes. In production the wipe belongs to
    `gunicorn.conf.py`'s `on_starting`, which runs in the master before any
    worker forks, and it has to stay the only thing that deletes: a value frozen
    in a file from a previous run is what keeps an exported total monotonic, and
    a management command that cleaned up after itself would be destroying a
    live gunicorn's counters.
    """
    os.makedirs(path, exist_ok=True)
    return path
