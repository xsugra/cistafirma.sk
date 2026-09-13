"""Rate limits for the two public endpoints that cost real work.

`CompanyViewSet` is `AllowAny`, so both scopes below are reachable without an
account: `report` renders a PDF through WeasyPrint (seconds of CPU per call)
and `peers` counts and sorts across the whole register. Until now neither had
any limit -- `REST_FRAMEWORK` in the settings module configured no throttle
classes anywhere in the project, so `DEFAULT_THROTTLE_RATES` was the only part
of DRF's throttling that existed, and only as an unused default.

Two decisions worth naming:

* **One class, keyed by user when there is one and by address otherwise.**
  DRF's own pair is `AnonRateThrottle` + `UserRateThrottle`, and each returns
  `None` for the other's requests -- so covering an endpoint that accepts both
  an account and no account takes two classes, and dropping either one is a
  hole that looks like a fitted limit. One class that picks its own key cannot
  be half-fitted.
* **It fails open, loudly.** A cache outage must not take the endpoint down
  with it, so the limiter allows the request -- but a limiter that has quietly
  stopped limiting is a control that reads healthy while doing nothing, so the
  first failure is logged at ERROR with the traceback. The rest drop to DEBUG,
  because the alternative is one traceback per request for the length of the
  outage.
"""

from __future__ import annotations

import logging

from rest_framework.throttling import SimpleRateThrottle

logger = logging.getLogger(__name__)

#: Module-level so an outage produces one traceback rather than one per
#: request. Not per-process state that anything else reads.
_cache_failure_logged = False


class PublicRateThrottle(SimpleRateThrottle):
    """A throttle for an endpoint that serves signed-in and anonymous callers.

    The address comes from `self.get_ident`, which is DRF's `NUM_PROXIES`
    handling of `X-Forwarded-For`. That setting is only correct relative to a
    deployment's proxy chain (see `THROTTLE_NUM_PROXIES` in the settings), so
    behind a longer chain than configured every caller would share one bucket
    -- an over-limit, which is the safe direction to be wrong in, but worth
    knowing before reading a 429 as one abuser.
    """

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = f'user:{request.user.pk}'
        else:
            ident = f'ip:{self.get_ident(request)}'
        return self.cache_format % {'scope': self.scope, 'ident': ident}

    def allow_request(self, request, view) -> bool:
        try:
            return super().allow_request(request, view)
        except Exception:
            global _cache_failure_logged
            if not _cache_failure_logged:
                _cache_failure_logged = True
                logger.exception(
                    'Throttle cache is unavailable -- rate limiting is off until it recovers.'
                )
            else:
                logger.debug('Throttle cache still unavailable.', exc_info=True)
            return True


class ReportThrottle(PublicRateThrottle):
    """Scope for `GET /api/companies/<ico>/report/`."""

    scope = 'report'


class PeersThrottle(PublicRateThrottle):
    """Scope for `GET /api/companies/<ico>/peers/`."""

    scope = 'peers'


class DocumentsThrottle(PublicRateThrottle):
    """Scope for the two `Účtovné závierky` document endpoints.

    Both are `AllowAny` and both spend requests against registeruz.sk, so both
    take the same bucket: a listing and the download it leads to are one
    intention, and splitting them into two scopes would let a caller spend the
    listing budget to enumerate years while the download budget stayed full.
    """

    scope = 'documents'
