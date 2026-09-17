"""Tests for the one place that settles prometheus_client's multiprocess mode.

Two halves, and they fail for different reasons.

The unit half pins the normalisation rules against explicit dicts, so it cannot
be perturbed by whatever the ambient environment happens to hold. It also pins
the one property of `ensure_multiproc_dir` that is load-bearing rather than
incidental: it creates, and never removes.

The subprocess half is the half that matters. `prometheus_client` picks its
value class exactly once per process, when `prometheus_client.values` is first
imported, and this test process has already picked it -- so the choice is not
observable from inside it, by any amount of monkeypatching. A fresh interpreter
is the only instrument that can see it. Each subprocess is handed an environment
the test controls completely, and asserts on the outcome rather than on the
call: where the counter files land, whether the directory exists, and whether
the process survives at all.

That last one is not decoration. A `PROMETHEUS_MULTIPROC_DIR` that is set to a
directory that does not exist does not cost `/metrics` -- it kills the process
at import, in the first `Counter(...)`. `docker compose run backend ...` is the
everyday command that does it, because the one-shot inherits the variable from
the service definition and never runs gunicorn, which was the only thing that
created the directory. `test_a_configured_directory_is_created_before_any_metric`
is the regression test for that.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from django.test import SimpleTestCase

from core.prometheus_env import ensure_multiproc_dir, normalize_multiproc_env

BACKEND_DIR = Path(__file__).resolve().parents[1]

_HAS_PROMETHEUS_CLIENT = importlib.util.find_spec("prometheus_client") is not None

# Runs in a fresh interpreter: settle the environment the way settings.py does,
# then report what the library decided. Printing JSON keeps the assertions in the
# test process instead of in the snippet's formatting.
_PROBE = """
import json, os, sys
sys.path.insert(0, %(backend)r)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
import django
django.setup()                      # imports companies.models, i.e. builds a metric
result = {
    "key_present": "PROMETHEUS_MULTIPROC_DIR" in os.environ,
    "value": os.environ.get("PROMETHEUS_MULTIPROC_DIR"),
    "cwd_db_files": sorted(f for f in os.listdir(".") if f.endswith(".db")),
}
try:
    from prometheus_client import values
    result["value_class"] = values.ValueClass.__name__
    # The library's own explicit discriminator. It is the right thing to assert
    # on: in multiprocess mode `ValueClass` is a class *defined inside* the
    # `MultiProcessValue` factory, so its name is `MmapedValue` -- a local class
    # name that could change without the behaviour changing. `_multiprocess` is
    # the flag the library sets on purpose, and it is False on `MutexValue`.
    result["multiprocess"] = getattr(values.ValueClass, "_multiprocess", None)
except Exception as exc:            # pragma: no cover - surfaced as a test failure
    result["value_class"] = "unavailable: %%s" %% type(exc).__name__
    result["multiprocess"] = None
print("PROBE" + json.dumps(result))
"""


def _probe(multiproc_value, cwd):
    """Run the probe in a fresh interpreter with a controlled environment.

    `multiproc_value` is what the process sees for `PROMETHEUS_MULTIPROC_DIR`:
    `None` removes the variable, a string sets it. Anything a `.env` file might
    want to say is overridden rather than merged -- `load_dotenv` does not
    replace a key that is already in the environment, so a value set here is the
    value settings.py normalises.
    """
    env = os.environ.copy()
    env.pop("PROMETHEUS_MULTIPROC_DIR", None)
    if multiproc_value is not None:
        env["PROMETHEUS_MULTIPROC_DIR"] = multiproc_value

    proc = subprocess.run(
        [sys.executable, "-c", _PROBE % {"backend": str(BACKEND_DIR)}],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    marker = [line for line in proc.stdout.splitlines() if line.startswith("PROBE")]
    if not marker:
        raise AssertionError(
            "probe produced no result\n"
            f"exit={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return json.loads(marker[-1][len("PROBE"):]), proc


class NormalizeMultiprocEnvTests(SimpleTestCase):
    """The rules, against explicit dicts rather than the real environment."""

    def test_absent_variable_stays_absent(self):
        environ = {}
        self.assertIsNone(normalize_multiproc_env(environ))
        self.assertNotIn("PROMETHEUS_MULTIPROC_DIR", environ)

    def test_empty_variable_is_removed_not_blanked(self):
        """The whole point: presence is what the library tests, so it must go.

        Leaving the key in place with an empty value is the bug -- the library
        would still enter multiprocess mode and memory-map into the working
        directory, while every reader in this repo would treat the feature as off.
        """
        environ = {"PROMETHEUS_MULTIPROC_DIR": ""}
        self.assertIsNone(normalize_multiproc_env(environ))
        self.assertNotIn("PROMETHEUS_MULTIPROC_DIR", environ)

    def test_whitespace_only_variable_is_removed(self):
        environ = {"PROMETHEUS_MULTIPROC_DIR": "   "}
        self.assertIsNone(normalize_multiproc_env(environ))
        self.assertNotIn("PROMETHEUS_MULTIPROC_DIR", environ)

    def test_surrounding_whitespace_is_trimmed_in_place(self):
        # The library would otherwise use the padded string as a path, and a
        # directory named " /tmp/x " is not one anybody meant to configure.
        environ = {"PROMETHEUS_MULTIPROC_DIR": "  /tmp/multiproc  "}
        self.assertEqual(normalize_multiproc_env(environ), "/tmp/multiproc")
        self.assertEqual(environ["PROMETHEUS_MULTIPROC_DIR"], "/tmp/multiproc")

    def test_ordinary_value_is_returned_unchanged(self):
        environ = {"PROMETHEUS_MULTIPROC_DIR": "/tmp/multiproc"}
        self.assertEqual(normalize_multiproc_env(environ), "/tmp/multiproc")
        self.assertEqual(environ["PROMETHEUS_MULTIPROC_DIR"], "/tmp/multiproc")


class EnsureMultiprocDirTests(SimpleTestCase):
    def test_missing_directory_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "nested", "multiproc")
            self.assertFalse(os.path.isdir(target))
            self.assertEqual(ensure_multiproc_dir(target), target)
            self.assertTrue(os.path.isdir(target))

    def test_existing_directory_is_left_alone(self):
        """It creates; it must never delete.

        In production the wipe belongs to gunicorn's `on_starting`, in the master,
        before any worker forks. A frozen counter file from a previous run is what
        keeps an exported total monotonic, so an `ensure` that cleaned up after
        itself would be destroying a live gunicorn's counters -- and it would do so
        from a management command nobody would think to suspect.
        """
        with tempfile.TemporaryDirectory() as tmp:
            survivor = os.path.join(tmp, "counter_4321.db")
            Path(survivor).write_bytes(b"frozen counter")
            self.assertEqual(ensure_multiproc_dir(tmp), tmp)
            self.assertTrue(os.path.exists(survivor), "ensure_multiproc_dir deleted a live counter file")

    def test_directory_path_is_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "multiproc")
            self.assertEqual(ensure_multiproc_dir(target), target)


@unittest.skipUnless(
    _HAS_PROMETHEUS_CLIENT,
    "prometheus_client is not installed, so its import-time choice cannot be observed",
)
class MultiprocModeInAFreshProcessTests(SimpleTestCase):
    """What the library actually does, in a process that has not decided yet."""

    def test_an_empty_variable_leaves_multiprocess_mode_off(self):
        with tempfile.TemporaryDirectory() as cwd:
            result, proc = _probe("", cwd)

            self.assertEqual(
                result["key_present"],
                False,
                "an empty PROMETHEUS_MULTIPROC_DIR survived normalisation, so "
                "prometheus_client will enter multiprocess mode while every reader "
                "in this repo treats the feature as off",
            )
            self.assertEqual(result["multiprocess"], False, f"value class was {result['value_class']}")
            # The symptom, not the cause: with an empty-but-present variable the
            # counters are memory-mapped through a *relative* path, so they land in
            # the process's working directory -- which in this stack is the
            # bind-mounted /app, i.e. the production checkout.
            self.assertEqual(
                result["cwd_db_files"],
                [],
                f"counter files were written into the working directory: {result['cwd_db_files']}",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_a_configured_directory_is_created_before_any_metric(self):
        """The regression test for `docker compose run backend ...` dying at import.

        A configured-but-missing directory is fatal rather than degrading, so
        settings.py has to create it before the first `Counter(...)` -- and the
        first metric in any Django process is built by `companies.models` during
        app-registry population, which is why the directory is ensured from
        settings.py and not from `core/metrics.py`.
        """
        with tempfile.TemporaryDirectory() as cwd, tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "multiproc")
            self.assertFalse(os.path.isdir(target), "precondition: directory must not exist")

            result, proc = _probe(target, cwd)

            self.assertEqual(proc.returncode, 0, f"process died at import:\n{proc.stderr}")
            self.assertTrue(
                os.path.isdir(target),
                "settings.py did not create the configured directory, so the first "
                "Counter(...) would have raised FileNotFoundError",
            )
            self.assertEqual(result["multiprocess"], True, f"value class was {result['value_class']}")
            self.assertEqual(result["value"], target)
            self.assertEqual(result["cwd_db_files"], [], "counter files leaked into the working directory")
