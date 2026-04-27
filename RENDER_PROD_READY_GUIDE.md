# Render Deployment + Seeding + Production Readiness Guide (`#codebase`)

This guide is tailored to your current Django repo (`playto_kyc`) and gives you a clean path to:

1. deploy successfully on Render,
2. seed initial users/data on the live environment,
3. harden the app for production use.

---

## 0) What this repo already has (good news)

- `Procfile` with Gunicorn:

```bash
web: gunicorn config.wsgi:application
```

- Static serving via WhiteNoise in `config/settings.py`.
- Seed command exists: `python manage.py seed`.
- Admin route exists at `/admin/`.

---

## 1) Fix deployment blockers first (mandatory)

Your current settings are still SQLite-first and permissive (`ALLOWED_HOSTS="*"` fallback). For Render production, switch to Postgres + strict envs.

### 1.1 Update dependencies

Add these to `requirements.txt`:

```txt
dj-database-url==2.2.0
psycopg[binary]==3.2.1
```

Then install locally:

```bash
pip install -r requirements.txt
```

---

### 1.2 Make database production-aware in `config/settings.py`

Add import:

```python
import dj_database_url
```

Replace `DATABASES` block with:

```python
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        ssl_require=not DEBUG,
    )
}
```

---

### 1.3 Lock down hosts and CSRF

Replace wildcard host fallback with strict defaults:

```python
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "DJANGO_ALLOWED_HOSTS",
        "localhost,127.0.0.1"
    ).split(",")
    if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

> Why: Render runs behind a proxy; this ensures Django correctly treats HTTPS requests as secure.

---

### 1.4 Keep docs conflict-free (recommended)

Ensure `README.md` and `EXPLAINER.md` stay free of merge-conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) before submission.

---

## 2) Configure Render services

## 2.1 Create Postgres on Render

1. In Render Dashboard → **New** → **PostgreSQL**.
2. Create DB and wait until status is available.
3. Copy the **Internal Database URL** (preferred for same-region private network).

---

## 2.2 Create/Update Web Service

1. Render Dashboard → **New Web Service** (or open existing one).
2. Connect this GitHub repo.
3. Runtime: Python.
4. Set commands:

```bash
# Build Command
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

```bash
# Start Command
gunicorn config.wsgi:application
```

5. Add **Pre-Deploy Command** (if available in your Render plan/UI):

```bash
python manage.py migrate
```

If pre-deploy is unavailable, run migration from Render Shell after each deploy:

```bash
python manage.py migrate
```

---

## 3) Set environment variables in Render

In Web Service → **Environment** set:

```txt
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<generate-a-strong-random-secret>
DJANGO_ALLOWED_HOSTS=playto-kyc-z65r.onrender.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://playto-kyc-z65r.onrender.com
DATABASE_URL=<from-render-postgres>
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
DJANGO_SECURE_HSTS_SECONDS=31536000
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=True
DJANGO_SECURE_HSTS_PRELOAD=True
```

Optional logging level:

```txt
KYC_LOG_LEVEL=INFO
```

---

## 4) Seed the live Render app (exact steps)

Open Render Web Service → **Shell** and run:

```bash
python manage.py migrate
python manage.py seed
```

This creates:

- reviewer: `reviewer1`
- merchants: `merchant1`, `merchant2`
- sample submissions (draft + under_review)

Default seed password in current code:

```txt
password123
```

> Immediately rotate passwords in production.

Rotate reviewer password:

```bash
python manage.py changepassword reviewer1
```

(Optional) create your own admin:

```bash
python manage.py createsuperuser
```

---

## 5) Post-deploy verification checklist

Run these checks in Render Shell:

```bash
python manage.py check
python manage.py check --deploy
python manage.py test
```

Then verify in browser:

- `https://playto-kyc-z65r.onrender.com/`
- `https://playto-kyc-z65r.onrender.com/admin/`
- `https://playto-kyc-z65r.onrender.com/api/v1/kyc/`

Expected:

- admin login loads,
- authenticated users can access API,
- reviewer can process queue actions.

---

## 6) Production hardening (recommended before final submission)

### 6.1 Move media files off local disk

Render filesystem is ephemeral for uploaded files in many deployment setups. Use S3/R2/GCS for `MEDIA_*` storage.

### 6.2 Restrict admin exposure

If possible:

- keep strong admin passwords,
- enable 2FA at org/account level,
- optionally IP-restrict admin via reverse proxy.

### 6.3 Improve auth for APIs

Current API uses Session + Basic auth. For production clients, add token/JWT auth.

### 6.4 Add monitoring/alerts

- monitor 5xx rates,
- monitor response latency,
- set alerts for failing health checks.

### 6.5 Backups

Enable automated DB backups in Render for Postgres.

---

## 7) Common failure fixes

### `DisallowedHost`
Set `DJANGO_ALLOWED_HOSTS` correctly with your Render domain.

### CSRF failure on admin login
Set `DJANGO_CSRF_TRUSTED_ORIGINS` including `https://<your-render-domain>`.

### Static files broken
Ensure build command includes:

```bash
python manage.py collectstatic --noinput
```

### Cannot log into admin with seed user
Re-run seed + reset password:

```bash
python manage.py seed
python manage.py changepassword reviewer1
```

---

## 8) Minimal release flow (repeat for each deploy)

```bash
# local
python manage.py test
python manage.py check --deploy
```

Push to GitHub → Render auto-deploys → run migrations if needed → verify `/admin/` + API endpoints.

---

## 9) Final “prod-ready” definition for this repo

You are production-ready when all are true:

- [ ] Using Render Postgres via `DATABASE_URL`
- [ ] `DJANGO_DEBUG=False`
- [ ] Strict `ALLOWED_HOSTS` + `CSRF_TRUSTED_ORIGINS`
- [ ] HTTPS/security cookie/HSTS envs enabled
- [ ] migrations applied on live
- [ ] seed executed (or real users created)
- [ ] passwords rotated from defaults
- [ ] `check --deploy` passes
- [ ] tests pass
- [ ] admin + API smoke tested on Render domain

---

If you want, next I can apply the exact `settings.py` + `requirements.txt` changes for you directly in code so this guide is fully implemented, not just documented.
