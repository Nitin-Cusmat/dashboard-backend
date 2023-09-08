# Base image
FROM python:3.11-slim

ARG django_settings_module=apiserver.settings

# ----- A GREEN_ENV="happy environment" -----
# 1. Do not buffer the output stream
# 2. Do not generate *.pyc files
# 3. Set timezone to UTC
# 4. Select the settings file to be used
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TZ=UTC
ENV DJANGO_SETTINGS_MODULE=${django_settings_module}

# Install vital elements
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    gdal-bin \
    libgdal-dev \
    && pip install --upgrade pip \
    && pip install gunicorn

# Construct the cockpit
RUN mkdir /code
WORKDIR /code

# Install app vital elements
COPY apiserver/requirements/common.txt .
COPY apiserver/requirements/dev.txt .
RUN pip install -r dev.txt
