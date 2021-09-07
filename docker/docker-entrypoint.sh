#!/bin/sh
set -e
/venv/bin/pip install -r pip.lock

until psql $DATABASE_URL -c '\l'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up - continuing"

/venv/bin/python manage.py migrate --noinput
/venv/bin/python manage.py collectstatic --noinput
/venv/bin/python manage.py createcachetable --noinput

exec "$@"
