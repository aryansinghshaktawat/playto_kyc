# Playto KYC Backend

A simple Django + Django REST Framework backend for a KYC submission workflow.

This project models how merchants submit KYC details and documents, while reviewers process those submissions through a controlled review lifecycle. It is designed to be clean, readable, and suitable for an internship-level backend project submission.

## Problem Statement

Merchants need a secure way to submit KYC information and documents. Reviewers need a controlled workflow to review submissions, request more information, approve, or reject them. This project solves that with:

- a structured KYC submission model
- strict state transitions
- backend file validation
- role-based access using Django's built-in authentication

## Features

- Merchant and KYC submission models
- DRF `ModelViewSet` API under `/api/v1/`
- State machine enforced inside the model
- File upload for PAN, Aadhaar, and bank statement
- File validation for type and size
- Reviewer vs merchant access control using `user.is_staff`
- Public read access for demo purposes, protected write access
- Dynamic SLA flag with `is_at_risk`
- Reviewer queue ordered oldest first
- Notification audit log for status changes

## Tech Stack

- Python 3.12
- Django 6
- Django REST Framework
- SQLite for local development

## Project Structure

Recommended structure for this repository:

```text
playto_kyc/
├── config/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── kyc/
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── EXPLAINER.md
├── manage.py
├── README.md
├── requirements.txt
└── .gitignore
```

Local-only files that should not be committed:

- `venv/`
- `db.sqlite3`
- `media/`
- `__pycache__/`
- `.env`

## Setup Instructions

1. Clone the repository

```bash
git clone <your-repo-url>
cd playto_kyc
```

2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies

```bash
pip install -r requirements.txt
```

4. Configure environment variables

```bash
export DJANGO_SECRET_KEY="your-local-secret-key"
export DJANGO_DEBUG="True"
export DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost"
```

5. Run migrations

```bash
python manage.py migrate
```

6. Start the development server

```bash
python manage.py runserver
```

The API will be available at:

- [http://127.0.0.1:8000/api/v1/kyc/](http://127.0.0.1:8000/api/v1/kyc/)

## Authentication and Access Control

This project uses Django's built-in `User` model.

- `is_staff = True` means reviewer
- `is_staff = False` means merchant

Access rules:

- Reviewers can see all submissions
- Merchants can only see submissions where `merchant.email == request.user.email`
- `GET` requests are temporarily public for demo purposes

## API Overview

Base path:

- `/api/v1/`

Main endpoint:

- `GET /api/v1/kyc/`
- `POST /api/v1/kyc/`
- `GET /api/v1/kyc/<id>/`
- `PATCH /api/v1/kyc/<id>/`
- `PUT /api/v1/kyc/<id>/`
- `DELETE /api/v1/kyc/<id>/`

Reviewer queue:

- `GET /api/v1/kyc/?queue=true`

## State Machine

Allowed transitions:

- `draft -> submitted`
- `submitted -> under_review`
- `under_review -> approved`
- `under_review -> rejected`
- `under_review -> more_info_requested`
- `more_info_requested -> submitted`

The logic lives inside the model so status rules are not scattered across views.

## File Upload Rules

Allowed file types:

- PDF
- JPG
- JPEG
- PNG

Maximum file size:

- 5 MB

Validation is enforced on the backend. Invalid uploads return HTTP `400` with a consistent error response.

## Example API Requests

### 1. Create a KYC submission

```bash
curl -u merchant1:password -X POST http://127.0.0.1:8000/api/v1/kyc/ \
  -F "business_name=Acme Pvt Ltd" \
  -F "business_type=Ecommerce" \
  -F "monthly_volume=250000" \
  -F "pan_document=@/absolute/path/pan.pdf" \
  -F "aadhaar_document=@/absolute/path/aadhaar.jpg" \
  -F "bank_statement=@/absolute/path/bank.png"
```

Example success response:

```json
{
  "id": 1,
  "merchant": 1,
  "business_name": "Acme Pvt Ltd",
  "business_type": "Ecommerce",
  "monthly_volume": 250000.0,
  "pan_document": "http://127.0.0.1:8000/media/kyc_documents/merchant_1/pan.pdf",
  "aadhaar_document": "http://127.0.0.1:8000/media/kyc_documents/merchant_1/aadhaar.jpg",
  "bank_statement": "http://127.0.0.1:8000/media/kyc_documents/merchant_1/bank.png",
  "status": "draft",
  "is_at_risk": false,
  "created_at": "2026-04-26T18:00:00Z",
  "updated_at": "2026-04-26T18:00:00Z"
}
```

### 2. Submit a draft KYC submission

```bash
curl -u merchant1:password -X PATCH http://127.0.0.1:8000/api/v1/kyc/1/ \
  -H "Content-Type: application/json" \
  -d '{"status":"submitted"}'
```

### 3. Reviewer queue

```bash
curl -u reviewer1:password "http://127.0.0.1:8000/api/v1/kyc/?queue=true"
```

## Example Error Responses

Invalid status transition:

```json
{
  "error": "Invalid status transition from 'draft' to 'approved'."
}
```

Invalid file type:

```json
{
  "error": "pan_document: Unsupported file type. Allowed types are: pdf, jpg, jpeg, png."
}
```

Oversized file:

```json
{
  "error": "pan_document: File size must not exceed 5 MB."
}
```

## How to Test

1. Start the server with `python manage.py runserver`
2. Open the DRF browsable API at [http://127.0.0.1:8000/api/v1/kyc/](http://127.0.0.1:8000/api/v1/kyc/)
3. Log in with a Django user
4. Use `multipart/form-data` for file uploads
5. Test valid and invalid transitions
6. Test merchant vs reviewer access using separate users

## Seed Data Instructions

Create a superuser or reviewer:

```bash
python manage.py createsuperuser
```

Then open the Django shell:

```bash
python manage.py shell
```

Run:

```python
from django.contrib.auth.models import User
from kyc.models import Merchant

reviewer = User.objects.create_user(
    username="reviewer1",
    email="reviewer@example.com",
    password="password123",
    is_staff=True,
)

merchant_user_1 = User.objects.create_user(
    username="merchant1",
    email="merchant1@example.com",
    password="password123",
    is_staff=False,
)

merchant_user_2 = User.objects.create_user(
    username="merchant2",
    email="merchant2@example.com",
    password="password123",
    is_staff=False,
)

Merchant.objects.create(
    name="Merchant One",
    email="merchant1@example.com",
    phone="9999999991",
)

Merchant.objects.create(
    name="Merchant Two",
    email="merchant2@example.com",
    phone="9999999992",
)
```

Note:

- merchant access depends on matching `Merchant.email` with `User.email`
- reviewer access depends on `User.is_staff = True`

## Deployment

Deployment link:

- `Add deployed API URL here`

## Submission Checklist

- `requirements.txt` is present
- `.gitignore` is present
- migrations are committed
- `venv/`, `db.sqlite3`, and `media/` are not committed
- API runs locally with `python manage.py runserver`
- reviewer and merchant flows both work
- file validation works
- state transitions are enforced

## Future Improvements

- Add automated tests for model transitions and API permissions
- Move secret and debug settings into a real `.env` workflow
- Add token-based authentication for frontend clients
- Add pagination and filtering for larger reviewer queues
