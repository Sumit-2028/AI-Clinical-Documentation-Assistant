FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY services/gateway/requirements.txt /app/services/gateway/requirements.txt
RUN pip install --no-cache-dir -r /app/services/gateway/requirements.txt

COPY . /app

EXPOSE 8000
