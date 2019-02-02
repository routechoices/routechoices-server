FROM python:3.6
ENV PYTHONUNBUFFERED 1
ENV C_FORCE_ROOT true
RUN mkdir /app
RUN mkdir /static
WORKDIR /app
ADD ./ /app
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
CMD python manage.py collectstatic --no-input;python manage.py migrate; gunicorn routechoices.wsgi -b 0.0.0.0:8000
