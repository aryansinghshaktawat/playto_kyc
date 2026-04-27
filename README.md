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

This project implements that system end-to-end.

---

##  Tech Stack

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

```bash id="4iqlh3"
python manage.py makemigrations
python manage.py migrate
```

---

### 5. Create Superuser

```bash id="4rt3bf"
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

---

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
