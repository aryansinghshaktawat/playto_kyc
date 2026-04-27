# KYC Submission & Review System

##  Overview

This project implements a **production-ready KYC (Know Your Customer) workflow system** using Django and Django REST Framework.

It is designed to simulate a real-world onboarding pipeline where merchants submit KYC details and reviewers process them through a controlled lifecycle.

---

##  Key Design Principles

* **State Machine Driven Workflow**
* **Role-Based Access Control**
* **Secure File Handling**
* **Scalable API Design**
* **Audit & Notification System**

---

##  KYC Lifecycle (State Machine)

The system enforces strict transitions:

```
Draft → Submitted → Under Review → Approved / Rejected
                          ↓
                  More Info Requested → Submitted
```

###  Allowed Transitions

| From                | To                                        |
| ------------------- | ----------------------------------------- |
| Draft               | Submitted                                 |
| Submitted           | Under Review                              |
| Under Review        | Approved / Rejected / More Info Requested |
| More Info Requested | Submitted                                 |

###  Invalid transitions are blocked at model level

This ensures:

* Data integrity
* No illegal state jumps
* Predictable workflow

---

## 👥 Roles & Permissions

###  Merchant

* Create KYC submission
* Upload required documents
* Submit KYC

###  Reviewer (Admin/Staff)

* View review queue
* Approve / Reject submissions
* Request additional information

###  Enforcement

* Merchants can only access their own data
* Review actions restricted to staff users

---

##  File Upload Handling

* Supported formats: **PDF, JPG, PNG**
* Max file size: **5MB**
* Validation includes:

  * Extension check
  * File size limit
* Files stored per merchant:

```
kyc_documents/<merchant_id>/
```

---

## ⏱ SLA Monitoring

Each submission is monitored for processing delay.

* SLA threshold: **24 hours**
* Submissions in `submitted` or `under_review`:

  * Marked `is_at_risk = true` if delayed

This helps identify bottlenecks in processing.

---

##  Reviewer Queue

Dedicated endpoint:

```
GET /api/v1/kyc/reviewer_queue/
```

* Returns submissions requiring action
* Sorted by creation time (FIFO)

---

##  Notification System

Every status change generates a notification:

```json
{
  "event_type": "status_changed",
  "from": "submitted",
  "to": "approved"
}
```

This enables:

* Audit trails
* Event tracking
* Future integrations (email/webhooks)

---

##  API Endpoints

### Merchant Actions

* `POST /api/v1/kyc/` → Create submission
* `POST /api/v1/kyc/{id}/submit/` → Submit KYC

---

### Reviewer Actions

* `POST /api/v1/kyc/{id}/approve/`
* `POST /api/v1/kyc/{id}/reject/`
* `POST /api/v1/kyc/{id}/request_info/`

---

### System Endpoints

* `GET /api/v1/kyc/reviewer_queue/`
* `GET /api/v1/kyc/at_risk/`

---

##  Technical Decisions

###  State Machine at Model Level

* Prevents bypass via API or admin
* Ensures business rules are always enforced

###  Atomic Transactions

* Guarantees consistency during create/update

###  Query Optimization

* Uses `select_related` for efficient joins

###  Separation of Concerns

* Models → Business logic
* Views → API control
* Serializers → Data validation

---

##  Challenges Faced

* Handling file uploads safely on limited storage (Render free tier)
* Preventing unauthorized status changes
* Designing a flexible but strict workflow system

---

##  Future Improvements

* JWT Authentication (instead of session-based)
* Cloud storage integration (AWS S3 / GCP)
* Async processing (Celery)
* Email/SMS notification system
* Reviewer assignment strategies (load balancing)

---

##  Conclusion

This system demonstrates:

* Real-world backend design
* Workflow enforcement using state machines
* Secure and scalable API architecture

It is structured to be **production-ready and extensible**.

---

# EXPLAINER.md

## 1) The State Machine

**Where it lives:** `kyc/models.py` in `KYCSubmission.transition_to()` and `ALLOWED_TRANSITIONS`.

```python
ALLOWED_TRANSITIONS = {
    STATUS_DRAFT: [STATUS_SUBMITTED],
    STATUS_SUBMITTED: [STATUS_UNDER_REVIEW],
    STATUS_UNDER_REVIEW: [STATUS_APPROVED, STATUS_REJECTED, STATUS_MORE_INFO_REQUESTED],
    STATUS_MORE_INFO_REQUESTED: [STATUS_SUBMITTED],
    STATUS_APPROVED: [],
    STATUS_REJECTED: [],
}

def transition_to(self, new_status, reason=None):
    if not self.can_transition(new_status):
        raise ValueError(f"Invalid transition {self.status} → {new_status}")
    ...
```

**How illegal transitions are prevented:**
- `can_transition()` checks `ALLOWED_TRANSITIONS`
- if invalid, `ValueError` is raised
- API catches this and returns HTTP 400 with a clear error message

---

## 2) The Upload

**Where validation happens:**
- Model validators in `kyc/models.py`:
  - `validate_file_size`
  - `validate_document_type`
- Serializer checks in `kyc/serializers/__init__.py` for cleaner API errors

```python
MAX_UPLOAD_SIZE = 5 * 1024 * 1024
ALLOWED_DOCUMENT_EXTENSIONS = ["pdf", "jpg", "jpeg", "png"]

def validate_file_size(file):
    if file.size > MAX_UPLOAD_SIZE:
        raise ValidationError("File must be ≤ 5MB")

def validate_document_type(file):
    ext = os.path.splitext(file.name)[1].lower().lstrip(".")
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValidationError("Invalid file type")
```

**If someone uploads 50MB:**
- validation fails
- API returns 400 with a clear message
- file is not persisted

---

## 3) The Queue

**Query used for reviewer queue:**

```python
class KYCSubmissionQuerySet(models.QuerySet):
    def reviewer_queue(self):
        return self.filter(status__in=REVIEWER_QUEUE_STATUSES).order_by("created_at")
```

**SLA `at_risk` flag (dynamic):**

```python
@property
def is_at_risk(self):
    if self.status not in AT_RISK_STATUSES:
        return False
    return self.created_at < timezone.now() - timedelta(hours=SLA_AT_RISK_HOURS)
```

**Why this approach:**
- queue is DB-filtered and oldest-first for fair processing
- SLA is computed dynamically so it cannot go stale

---

## 4) The Auth

**How merchant A is blocked from seeing merchant B data:** `kyc/views.py` in `get_queryset()`.

```python
def get_queryset(self):
    user = self.request.user
    if user.is_staff:
        return self.queryset
    return self.queryset.filter(merchant__email=user.email)
```

Also:
- create/update/list require authentication
- reviewer-only actions (`start_review`, `approve`, `reject`, `request_info`, `reviewer_queue`, `at_risk`, `reviewer_metrics`) require `IsAdminUser`

---

## 5) The AI Audit

**Buggy AI suggestion I rejected:**
- AI suggested assigning merchant with `Merchant.objects.first()` as a fallback for unauthenticated requests.

**Why it was bad/insecure:**
- could attach submission to wrong merchant
- breaks tenant isolation
- violates business rule that submission owner must match logged-in merchant

**What I replaced it with:**

```python
def _get_merchant(self):
    user = self.request.user
    if not user.email:
        raise ValidationError("Authenticated user must have an email to submit KYC.")

    merchant, _ = Merchant.objects.get_or_create(
        email=user.email,
        defaults={"name": user.username or user.email, "phone": "9999999999"}
    )
    return merchant
```

This ensures merchant ownership is deterministic and tied to authenticated identity.
