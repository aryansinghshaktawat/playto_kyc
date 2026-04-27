# One-container Docker deployment

This repository includes a single Docker image which contains everything needed to run the Django app in production with an embedded SQLite database (no external Postgres required).

Features
- Single container: app + all dependencies
- Uses SQLite by default so you don't need to spin up a separate database server
- Gunicorn + WhiteNoise for production serving
- Entrypoint runs migrations and collectstatic automatically

Quick start (build & run):

```bash
# Build image
docker build -t playto_kyc:latest .

# Run container (detached)
docker run -d -p 8000:8000 --name playto_kyc playto_kyc:latest
```

Or using docker-compose (recommended for local testing):

```bash
docker-compose up -d --build
```

Notes
- Using SQLite inside a single container is convenient but not suitable for high-traffic, multi-replica deployments. For production durability across restarts/replicas, move to an external database (Postgres) and external object storage for media.
- If you want to use Postgres later, set DATABASE_URL in the environment to a Postgres connection string and the container will use it.
