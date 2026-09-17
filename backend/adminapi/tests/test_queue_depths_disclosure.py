"""A broker outage must not put the Redis DSN in the response body.

`queue_depths_view` catches a connection failure and used to return
`str(exc)` to the caller. redis-py and kombu put the connection URL in that
message, and `REDIS_URL` may embed a password — so a broker outage would
have handed a credential to the browser, where it lands in devtools, in
screenshots and in any error report the operator pastes.

The endpoint is staff-only, which lowers the exposure but does not change
what the response should carry: the name of the dependency that is down,
not its credentials.
"""

from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from backend.celery import app as celery_app
from users.models import User


class QueueDepthsDisclosureTests(TestCase):
    URL = "/api/admin/sync/queues/"

    def setUp(self):
        self.staff = User.objects.create_user(
            email="admin@example.com", password="testpass123", is_staff=True
        )
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def test_a_broker_failure_keeps_the_dsn_out_of_the_response(self):
        dsn = "redis://:hunter2@redis:6379/0"
        with patch.object(
            celery_app, "connection_or_acquire", side_effect=ConnectionError(dsn)
        ):
            with self.assertLogs("adminapi.views.sync", level="ERROR") as captured:
                response = self.client.get(self.URL)

        self.assertEqual(response.status_code, 502)
        body = response.content.decode()
        self.assertNotIn("hunter2", body)
        self.assertNotIn("redis://", body)
        # The detail is not lost -- it is in the log, which is where it belongs.
        self.assertIn("hunter2", "\n".join(captured.output))
        # The queue map is still returned, so a partial answer stays useful.
        self.assertIn("queues", response.data)
