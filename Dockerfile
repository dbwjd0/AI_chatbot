FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    default-libmysqlclient-dev \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

COPY . /app

ENV DJANGO_SETTINGS_MODULE=aibuddy_project.settings

EXPOSE 8000
CMD ["gunicorn", "aibuddy_project.wsgi:application", "--bind", "0.0.0.0:8000"]

