# Playto KYC Pipeline (Django + DRF)

A production-style KYC onboarding backend where merchants submit KYC details and reviewers process them through a strict state machine.

## Features

- Merchant KYC creation and updates
- Document upload: PAN, Aadhaar, bank statement
- Strict workflow transitions
- Reviewer queue (oldest first)
- Dynamic SLA flag (`is_at_risk`) for items older than 24 hours
- Notification event logging on status changes
- Role-based access control (merchant vs reviewer)
- Seed command for demo/test users

## Tech Stack

- Django 5
- Django REST Framework
- SQLite (local) / PostgreSQL (production via `DATABASE_URL`)
- Gunicorn + WhiteNoise

## API Base

All endpoints are under:

- `/api/v1/`

Main resource:

- `GET /api/v1/kyc/`
- `POST /api/v1/kyc/`
- `GET /api/v1/kyc/{id}/`
- `PATCH /api/v1/kyc/{id}/`

Transition endpoints:

- `POST /api/v1/kyc/{id}/transition/` (generic transition endpoint)
- `POST /api/v1/kyc/{id}/submit/`
- `POST /api/v1/kyc/{id}/start_review/`
- `POST /api/v1/kyc/{id}/approve/`
- `POST /api/v1/kyc/{id}/reject/`
- `POST /api/v1/kyc/{id}/request_info/`

Reviewer/system endpoints:

- `GET /api/v1/kyc/reviewer_queue/`
- `GET /api/v1/kyc/at_risk/`
- `GET /api/v1/kyc/reviewer_metrics/`

Admin:

- `/admin/`

## State Machine

Allowed transitions:

- `draft -> submitted`
- `submitted -> under_review`
- `under_review -> approved`
- `under_review -> rejected`
- `under_review -> more_info_requested`
- `more_info_requested -> submitted`

Illegal transitions return HTTP 400 with a clear message.

## File Upload Rules

- Allowed extensions: `pdf`, `jpg`, `jpeg`, `png`
- Max file size: `5MB`
- Server-side checks include:
  - extension validation
  - size validation
  - file signature/header validation (magic bytes)

## Local Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed
python manage.py runserver
```

## Seed Data

```bash
python manage.py seed
```

Creates/updates:

- reviewer user: `reviewer1` (staff/superuser)
- merchant users: `merchant1`, `merchant2`
- two merchant records
- one draft submission + one under_review submission

Default seeded password:

- `password123`

Rotate passwords in production immediately.

## Tests

```bash
python manage.py test -v 2
```

Includes tests for:

- illegal transitions (e.g., `draft -> approved`)
- transition endpoint validation
- missing-doc submission rejection
- merchant authorization isolation
- invalid file type/signature rejection
- reviewer permissions and metrics

## Production / Render

See:

- `RENDER_PROD_READY_GUIDE.md`

That file contains exact environment variables, deployment commands, seeding, and troubleshooting.

## Notes

- This repo uses local filesystem for media by default.
- For production durability on PaaS, move media to S3/R2/GCS.
