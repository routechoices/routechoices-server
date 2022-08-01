FROM python:3.10-slim

RUN mkdir /app/

# Copy in your requirements file
WORKDIR /app/
ADD . /app/

RUN set -ex \
    && apt-get update && apt-get install -y libgdal-dev g++ git libmagic-dev libgl1 watchman libpq5 --no-install-recommends \
    && python -m venv /venv \
    && /venv/bin/pip install --upgrade pip \
    && /venv/bin/pip --no-cache-dir install -r /app/requirements.txt \
    && apt-get autoremove -y \
    && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Copy your application code to the container (make sure you create a .dockerignore file if any large files or directories should be excluded)


# Install build deps, then run `pip install`, then remove unneeded build deps all in a single step. Correct the path to your production requirements file, if needed.

# uWSGI will listen on this port
EXPOSE 8000
#
EXPOSE 2000
EXPOSE 2002

# Add any custom, static environment variables needed by Django or your settings file here:
ENV DJANGO_SETTINGS_MODULE=routechoices.settings

# uWSGI configuration (customize as needed):
# ENV UWSGI_VIRTUALENV=/venv UWSGI_WSGI_FILE=routechoices/wsgi.py UWSGI_HTTP=:8000 UWSGI_MASTER=1 UWSGI_WORKERS=2 UWSGI_THREADS=8 UWSGI_UID=1000 UWSGI_GID=2000 UWSGI_LAZY_APPS=1 UWSGI_WSGI_ENV_BEHAVIOR=holy

# Call collectstatic (customize the following line with the minimal environment variables needed for manage.py to run):
RUN DATABASE_URL=none /venv/bin/python manage.py collectstatic --noinput
# ENTRYPOINT ["/app/docker-entrypoint.sh"]
# Start uWSGI
# CMD ["/venv/bin/uwsgi", "--http-auto-chunked", "--http-keepalive"]

ADD docker/wait-for-it.sh /wait-for-it.sh
RUN chmod 755 /wait-for-it.sh
