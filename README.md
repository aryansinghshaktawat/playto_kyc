#  Playto KYC Pipeline — Backend Assignment

A production-style **KYC onboarding system** built using Django and Django REST Framework.

This service allows merchants to submit KYC details and reviewers to process them through a controlled workflow with strict state transitions, file validation, and SLA tracking.

---

##  What This Project Solves

Playto Pay requires a robust onboarding pipeline where:

* Merchants submit business + identity details
* Reviewers validate submissions
* System enforces workflow rules
* Edge cases (invalid transitions, file validation, delays) are handled

<<<<<<< HEAD
This project implements that system end-to-end.

---

##  Tech Stack
=======
- Merchant and KYC submission models
- State machine enforced inside the model
- File upload for PAN, Aadhaar, and bank statement
- File validation for type and size
## Tech Stack

- Django REST Framework
- SQLite for local development
>>>>>>> 8c41aed (refactor: enhance KYC workflow documentation, improve state transition handling, and add reviewer metrics endpoint; update seed data command)

* **Backend**: Django, Django REST Framework
* **Database**: SQLite (can switch to PostgreSQL)
* **Auth**: Session-based authentication
* **Storage**: Local file storage (media/)

---

##  Core Features

### 1. Merchant KYC Submission

* Create and update KYC details
* Upload documents (PAN, Aadhaar, Bank Statement)
* Submit application for review

---

### 2. Reviewer Workflow (State Machine)

```id="1m7oqg"
draft → submitted → under_review → approved / rejected
                      ↓
              more_info_requested → submitted
```

* Invalid transitions are blocked at the model layer
* Ensures strict business logic enforcement

---

### 3. File Upload Validation

* Allowed formats: **PDF, JPG, PNG**
* Max size: **5MB**
* Validation includes:

  * File extension
  * File size
  * Basic file integrity checks

---

### 4. Reviewer Queue

```id="04sksl"
GET /api/v1/kyc/reviewer_queue/
```

* Returns submissions needing review
* Sorted FIFO (oldest first)

---

### 5. SLA Tracking

* Submissions older than **24 hours**
* Automatically flagged as:

```id="u1gt2x"
is_at_risk = true
```

* Helps detect delays in processing

---

### 6. Notifications System

Every status change generates an event:

```json id="x6fy0n"
{
  "event_type": "status_changed",
  "from": "submitted",
  "to": "approved"
}
```

Stored in database for audit and future integrations.

---

### 7. Role-Based Access

| Role     | Access                    |
| -------- | ------------------------- |
| Merchant | Own submissions only      |
| Reviewer | All submissions + actions |

---

##  API Endpoints

### Merchant Actions

* `POST /api/v1/kyc/` → Create submission
* `GET /api/v1/kyc/` → List own submissions
* `POST /api/v1/kyc/{id}/submit/` → Submit KYC

---

### Reviewer Actions

* `POST /api/v1/kyc/{id}/approve/`
* `POST /api/v1/kyc/{id}/reject/`
* `POST /api/v1/kyc/{id}/request_info/`

---

### System

* `GET /api/v1/kyc/reviewer_queue/`
* `GET /api/v1/kyc/at_risk/`

---

##  Running Locally

### 1. Clone Repo

```bash id="1zclxm"
git clone <your-repo-url>
cd <repo>
```

---

### 2. Create Virtual Environment

```bash id="lix23s"
python3 -m venv venv
source venv/bin/activate
```

---

### 3. Install Dependencies

```bash id="99tfmt"
pip install -r requirements.txt
```

---

### 4. Migrate DB

<<<<<<< HEAD
```bash id="4iqlh3"
python manage.py makemigrations
=======
5. Run migrations
>>>>>>> 8c41aed (refactor: enhance KYC workflow documentation, improve state transition handling, and add reviewer metrics endpoint; update seed data command)
python manage.py migrate
```

---

### 5. Create Superuser

<<<<<<< HEAD
<<<<<<< HEAD
```bash id="4rt3bf"
=======
The API will be available at:

- [http://127.0.0.1:8000/api/v1/kyc/](http://127.0.0.1:8000/api/v1/kyc/)

## Authentication and Access Control

=======
>>>>>>> 8c41aed (refactor: enhance KYC workflow documentation, improve state transition handling, and add reviewer metrics endpoint; update seed data command)
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

### Automated test run

```bash
python manage.py test -v 2
```

What is covered:

- valid state transition (`submitted -> under_review`)
- invalid transition rejection (`draft -> approved`)
- file validation (invalid file type rejected)
- permission enforcement (merchant cannot approve)
- auto merchant assignment from logged-in user email

## Seed Data Instructions

Create a superuser or reviewer:

```bash
>>>>>>> 9e5cee1 (refactor: enhance KYC submission workflow with improved state transitions, validation, and error handling; add automated tests and seed data command)
python manage.py createsuperuser
```

---

### 6. Run Server

```bash id="2rg5ae"
python manage.py runserver
```

---

### 7. Access API

* API Root:

```id="w3y9ds"
http://127.0.0.1:8000/api/v1/
```

* Login:

```id="ozq6l8"
http://127.0.0.1:8000/api-auth/login/
```

<<<<<<< HEAD
---
=======
### Recommended one-command seed

```bash
python manage.py seed
```

This command creates/updates:

- reviewer admin user: `reviewer1` / `password123`
- merchant user: `merchant1` / `password123`
- merchant user: `merchant2` / `password123`
- merchant records for `merchant1@example.com` and `merchant2@example.com`

## Known Limitations

- File uploads currently use local filesystem storage; on Render/PaaS this can be ephemeral.
  Use S3/R2/GCS for persistent production storage.
- Merchant linkage is based on matching `User.email` and `Merchant.email`.
  If they do not match, a merchant record will be auto-created on first submission.
- This project currently uses session auth for local testing; token/JWT auth can be added for frontend/mobile clients.

## Deployment
>>>>>>> 9e5cee1 (refactor: enhance KYC submission workflow with improved state transitions, validation, and error handling; add automated tests and seed data command)

##  Seed Data

Create:

* 2 merchants (via signup or DB)
* 1 reviewer (superuser)

Optional: Use Django shell to insert test data.

---

##  Design Decisions

### State Machine at Model Layer

* Prevents illegal transitions globally
* Cannot be bypassed via API/admin

---

### Strict Validation

* File validation ensures security
* Status validation ensures correctness

---

### Clean Separation

* Models → business rules
* Views → API handling
* Serializers → validation

---

##  Limitations

* Uses local storage (not scalable for production)
* Session auth instead of JWT
* Basic reviewer assignment (first available)

---

##  Future Improvements

* AWS S3 / Cloudinary storage
* JWT Authentication
* Async processing (Celery)
* Email notifications
* Reviewer load balancing

---

##  Deployment

Deployed on: **Render / Railway / etc.**
(Provide your live URL here)

---

##  What I’m Most Proud Of

* Clean state machine implementation
* Handling edge cases (invalid transitions, file validation)
* Building a system that mimics real-world onboarding flows

---

##  What I Would Improve With More Time

* Better frontend (React dashboard)
* Cloud storage integration
* Advanced reviewer assignment logic
* More test coverage

---

##  Author

Aryan Singh Shaktawat
