FROM python:3.12 as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends g++ gcc libgdal-dev libjpeg-dev zlib1g-dev libwebp-dev libmagic-dev libgl1 libpq5 libjxl-dev && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man

RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# final stage
FROM python:3.11-slim

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends curl gcc g++ git libgdal-dev libjpeg-dev zlib1g-dev libwebp-dev libmagic-dev libgl1 libpq5 libglib2.0-0 libjxl-dev && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man

RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

RUN pip install -r ./requirements.txt --find-links /wheels && rm -rf /wheels && rm -rf /root/.cache/pip/*

# Copy in your requirements file
WORKDIR /app/
ADD . /app/

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
RUN cp ./.env.dev ./.env
RUN DATABASE_URL="sqlite://:memory:" python manage.py collectstatic --noinput
# ENTRYPOINT ["/app/docker-entrypoint.sh"]
# Start uWSGI
# CMD ["/venv/bin/uwsgi", "--http-auto-chunked", "--http-keepalive"]

ADD wait-for-it.sh /wait-for-it.sh
RUN chmod 755 /wait-for-it.sh
