#!/bin/sh
set -e

/venv/bin/python manage.py migrate --noinput
/venv/bin/python manage.py collectstatic --noinput

exec "$@"
