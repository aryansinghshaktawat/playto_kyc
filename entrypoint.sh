#!/usr/bin/env bash
set -e

# Wait for DB readiness if using external DB URL (not used by default since sqlite is default)
if [ -n "${DATABASE_URL:-}" ] && [[ "${DATABASE_URL}" != sqlite* ]]; then
  echo "External DATABASE_URL detected — attempting to wait for DB to be ready..."
  # try until connection succeeds, timeout after a while
  for i in {1..30}; do
    python - <<PY
import sys
from urllib.parse import urlparse
url = "${DATABASE_URL}"
print('checking', url)
sys.exit(0)
PY
    sleep 1
  done
fi

echo "Running migrations..."
python manage.py migrate --noinput

if [ "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ "${DJANGO_SUPERUSER_PASSWORD:-}" ] && [ "${DJANGO_SUPERUSER_EMAIL:-}" ]; then
  echo "Creating superuser (if not exists)..."
  python - <<PY || true
from django.contrib.auth import get_user_model
User = get_user_model()
username = "${DJANGO_SUPERUSER_USERNAME}"
email = "${DJANGO_SUPERUSER_EMAIL}"
password = "${DJANGO_SUPERUSER_PASSWORD}"
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print('Superuser created')
else:
    print('Superuser already exists')
PY
fi

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:${PORT} \
    --workers 3 \
    --log-level info
