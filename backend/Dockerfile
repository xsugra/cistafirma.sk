FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (gunicorn is pinned in requirements.txt)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Static files for the Django admin, DRF and unfold. This pass exists so the
# image is runnable on its own, and because the image layer is what a fresh
# named volume at /app/staticfiles is seeded from; the backend container also
# collects again at start-up, with its real environment (docker-compose.yml).
#
# SECRET_KEY is passed on the command line rather than inherited from an env
# file: no env file may be in the build context (see .dockerignore), and
# settings.py refuses to import without a key once DEBUG is false. This value is
# a placeholder that satisfies that check and nothing else -- collectstatic
# hashes file contents and never the key, so no key material reaches the output.
#
# There is deliberately no `|| true`. It used to be here, and it is why the step
# could sit broken indefinitely: without an env file in the context the import
# raised ImproperlyConfigured, the `|| true` swallowed it, and the build shipped
# an image with no /app/staticfiles at all -- which is exactly what every image
# built on dell contained until 2026-09-15. A build that cannot collect its own
# static files must fail here rather than at the first admin page.
RUN SECRET_KEY=build-only-placeholder python manage.py collectstatic --noinput --settings=backend.settings

# Expose port
EXPOSE 8000

# Readiness probe: hits /healthz/ (DB + Redis round-trip). urllib is stdlib
# (slim has no curl); a 503 raises HTTPError -> exit 1 -> unhealthy.
# Workers/beat share this image but don't run gunicorn — they disable the
# healthcheck at the compose level.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 CMD ["python", "-c", "import sys,urllib.request as r; r.urlopen('http://127.0.0.1:8000/healthz/', timeout=4); sys.exit(0)"]

# Default command (can be overridden in docker-compose)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "backend.wsgi:application"]
