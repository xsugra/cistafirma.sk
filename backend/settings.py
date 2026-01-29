"""
Compatibility settings module.

This lets tools run from the repo root (where "backend" is a namespace
package) while keeping the original Django settings in backend/backend.
"""

from backend.backend.settings import *  # noqa: F403,F401

# Ensure Django imports URLs/WSGI from the inner settings package.
ROOT_URLCONF = "backend.backend.urls"
WSGI_APPLICATION = "backend.backend.wsgi.application"
