# Dockerfile
FROM python:3.10

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    python3-dev \
    libjpeg8-dev \
    zlib1g-dev \
    curl

# Install CouchDB Python client if needed
RUN pip install couchdb

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app/

RUN python src/manage.py collectstatic --noinput

CMD ["gunicorn", "--chdir", "src", "--bind", "0.0.0.0:8000", "grm.wsgi:application"]