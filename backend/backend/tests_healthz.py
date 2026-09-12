"""`/healthz` must not print a dependency's connection string to the world.

The readiness probe caught each dependency failure and put `str(exc)` in the
body. A Redis failure raised by `cache.set` carries the URL it could not
reach, and `REDIS_URL` may embed a password -- so a degraded stack would
answer an unauthenticated GET with `redis://:hunter2@redis:6379/0`.

Nothing reads that body to decide anything: the Docker healthcheck and the
Kubernetes probes look only at the status code. The detail is for a human, and
a human debugging a degraded stack reads the container log, where the
traceback now goes. So the body names which dependency is down and keeps the
rest for callers on a private address -- which is what both real probe paths
are, so the probe loses nothing.
"""

from unittest.mock import patch

from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings

# A genuinely routable address, so `is_internal_client` answers False. Not
# 203.0.113.x: see the class docstring.
PUBLIC_IP = "93.184.216.34"


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class HealthzDisclosureTests(TestCase):
    """`REMOTE_ADDR` decides whether the body may name the exception.

    Amusing trap: an address from the documentation ranges (203.0.113.0/24,
    198.51.100.0/24, 192.0.2.0/24) is *not* usable to model an outside caller
    here. `ipaddress` classifies those as private -- they are IANA
    special-purpose, not routable -- so `is_internal_client` says yes and the
    test would assert the opposite of what it means to.
    """

    def _fail_the_cache(self):
        return patch.object(
            cache, "set", side_effect=ConnectionError("redis://:hunter2@redis:6379/0")
        )

    def _fail_the_database(self):
        return patch.object(
            connection,
            "cursor",
            side_effect=RuntimeError("could not connect to server: cistafirma_db"),
        )

    def test_a_public_caller_learns_which_dependency_is_down_and_nothing_more(self):
        # REMOTE_ADDR is what `is_internal_client` reads; the test client's
        # default ("127.0.0.1") is loopback, so it has to be set explicitly to
        # model a caller that is not on the private network.
        with self._fail_the_cache():
            with self.assertLogs("backend.urls", level="ERROR") as captured:
                response = self.client.get("/healthz/", REMOTE_ADDR=PUBLIC_IP)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "degraded")
        self.assertEqual(response.json()["redis"], "error")

        body = response.content.decode()
        self.assertNotIn("hunter2", body)
        self.assertNotIn("redis://", body)
        # The detail is not lost -- it moved to the log.
        self.assertIn("hunter2", "\n".join(captured.output))

    def test_a_private_caller_keeps_the_detail_the_probe_used_to_carry(self):
        # The in-cluster kubelet probe and the Docker healthcheck both arrive
        # from private addresses, so the operator's `curl` from inside the pod
        # still says what broke.
        with self._fail_the_cache():
            with self.assertLogs("backend.urls", level="ERROR"):
                response = self.client.get("/healthz/", REMOTE_ADDR="10.0.0.7")

        self.assertEqual(response.status_code, 503)
        self.assertIn("hunter2", response.json()["redis"])

    def test_a_database_failure_is_named_without_the_exception(self):
        with self._fail_the_database():
            with self.assertLogs("backend.urls", level="ERROR") as captured:
                response = self.client.get("/healthz/", REMOTE_ADDR=PUBLIC_IP)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["db"], "error")
        self.assertNotIn("cistafirma_db", response.content.decode())
        self.assertIn("cistafirma_db", "\n".join(captured.output))

    def test_a_healthy_stack_says_so_and_names_both_dependencies(self):
        response = self.client.get("/healthz/", REMOTE_ADDR=PUBLIC_IP)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["db"], "ok")
        # The latency figure is not an exception and is not withheld -- it is
        # the one number an operator wants from a healthy probe.
        self.assertTrue(payload["redis"].startswith("ok ("))
