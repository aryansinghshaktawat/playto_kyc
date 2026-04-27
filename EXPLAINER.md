# EXPLAINER.md

## 1) The State Machine

**Where it lives:** `kyc/models.py` in `ALLOWED_TRANSITIONS` + `KYCSubmission.transition_to()`.

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
        allowed_next = ALLOWED_TRANSITIONS.get(self.status, [])
        raise ValueError(
            f"Invalid transition {self.status} → {new_status}. "
            f"Allowed: {allowed_next if allowed_next else 'no further transitions'}"
        )
    ...
```

**How illegal transitions are blocked:** all transition endpoints call `transition_to()`. If transition is illegal, API returns HTTP 400 with the model error message.

---

## 2) The Upload

**Where validation happens:** model validators in `kyc/models.py` and serializer checks in `kyc/serializers/__init__.py`.

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

def validate_document_signature(file):
    header = file.read(16)
    ...
    if ext == "pdf" and not header.startswith(b"%PDF-"):
        raise ValidationError("Invalid PDF file signature")
```

**If someone uploads a 50MB file:** validation fails immediately with HTTP 400 (`File must be ≤ 5MB`), and the file is not accepted.

---

## 3) The Queue

**Query powering reviewer queue (`oldest first`):**

```python
class KYCSubmissionQuerySet(models.QuerySet):
    def reviewer_queue(self):
        return self.filter(status__in=[STATUS_SUBMITTED, STATUS_UNDER_REVIEW]).order_by("created_at")
```

**SLA flag (`at_risk`) is computed dynamically:**

```python
@property
def is_at_risk(self):
    if self.status not in [STATUS_SUBMITTED, STATUS_UNDER_REVIEW]:
        return False
    return self.created_at < timezone.now() - timedelta(hours=24)
```

**Why this approach:** queue filtering is DB-driven and deterministic; `is_at_risk` is computed at read time so it never becomes stale.

---

## 4) The Auth

**Merchant A cannot see Merchant B data check (`kyc/views.py`):**

```python
def get_queryset(self):
    user = self.request.user
    if user.is_staff:
        return self.queryset
    return self.queryset.filter(merchant__email=user.email)
```

**Reviewer-only actions:** `start_review`, `approve`, `reject`, `request_info`, `reviewer_queue`, `at_risk`, and `reviewer_metrics` use `IsAdminUser`.

**Generic transition endpoint (`/api/v1/kyc/{id}/transition/`):** role checks are explicit:
- merchant can only transition to `submitted`
- reviewer can transition to review statuses (`under_review`, `approved`, `rejected`, `more_info_requested`)

---

## 5) The AI Audit

**Buggy AI output I rejected:** AI suggested fallback ownership like:

```python
merchant = Merchant.objects.first()
```

for submission creation when user mapping failed.

**Why this is insecure:** it can attach merchant A’s submission to merchant B (tenant data isolation bug).

**What I replaced it with:** deterministic mapping to authenticated identity:

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

This guarantees ownership and prevents cross-tenant leakage.
