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

# Collect static files
RUN python manage.py collectstatic --noinput --settings=backend.settings || true

# Expose port
EXPOSE 8000

# Readiness probe: hits /healthz/ (DB + Redis round-trip). urllib is stdlib
# (slim has no curl); a 503 raises HTTPError -> exit 1 -> unhealthy.
# Workers/beat share this image but don't run gunicorn — they disable the
# healthcheck at the compose level.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 CMD ["python", "-c", "import sys,urllib.request as r; r.urlopen('http://127.0.0.1:8000/healthz/', timeout=4); sys.exit(0)"]

# Default command (can be overridden in docker-compose)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "backend.wsgi:application"]
