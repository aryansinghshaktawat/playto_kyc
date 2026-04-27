FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off

WORKDIR /app

# system deps (kept minimal). libpq-dev is useful if psycopg needs building.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       libpq-dev \
       curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pip requirements first for better caching
COPY requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install -r /app/requirements.txt

# Copy project
COPY . /app/

# Ensure directories for runtime artifacts
RUN mkdir -p /app/staticfiles /app/media /data \
    && chown -R root:root /app

# Entrypoint will run migrations + collectstatic then start gunicorn
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENV PORT=8000

CMD ["/entrypoint.sh"]
