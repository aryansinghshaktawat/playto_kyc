import os
import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

# ================== CONSTANTS ==================

MAX_UPLOAD_SIZE = 5 * 1024 * 1024

ALLOWED_DOCUMENT_EXTENSIONS = ["pdf", "jpg", "jpeg", "png"]

STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
STATUS_UNDER_REVIEW = "under_review"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_MORE_INFO_REQUESTED = "more_info_requested"

STATUS_CHOICES = [
    (STATUS_DRAFT, "Draft"),
    (STATUS_SUBMITTED, "Submitted"),
    (STATUS_UNDER_REVIEW, "Under Review"),
    (STATUS_APPROVED, "Approved"),
    (STATUS_REJECTED, "Rejected"),
    (STATUS_MORE_INFO_REQUESTED, "More Info Requested"),
]

ALLOWED_TRANSITIONS = {
    STATUS_DRAFT: [STATUS_SUBMITTED],
    STATUS_SUBMITTED: [STATUS_UNDER_REVIEW],
    STATUS_UNDER_REVIEW: [STATUS_APPROVED, STATUS_REJECTED, STATUS_MORE_INFO_REQUESTED],
    STATUS_MORE_INFO_REQUESTED: [STATUS_SUBMITTED],
    STATUS_APPROVED: [],
    STATUS_REJECTED: [],
}

SLA_AT_RISK_HOURS = 24

REVIEWER_QUEUE_STATUSES = [STATUS_SUBMITTED, STATUS_UNDER_REVIEW]
AT_RISK_STATUSES = [STATUS_SUBMITTED, STATUS_UNDER_REVIEW]

# ================== VALIDATORS ==================

def validate_file_size(file):
    if file.size > MAX_UPLOAD_SIZE:
        raise ValidationError("File must be ≤ 5MB")


def validate_document_type(file):
    ext = os.path.splitext(file.name)[1].lower().lstrip(".")
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValidationError("Invalid file type")


def validate_document_signature(file):
    ext = os.path.splitext(file.name)[1].lower().lstrip(".")

    # Read small header bytes without breaking later file handling.
    current_pos = None
    if hasattr(file, "tell") and hasattr(file, "seek"):
        try:
            current_pos = file.tell()
        except Exception:
            current_pos = None

    header = file.read(16)

    if current_pos is not None:
        file.seek(current_pos)

    if ext == "pdf" and not header.startswith(b"%PDF-"):
        raise ValidationError("Invalid PDF file signature")

    if ext in ("jpg", "jpeg") and not header.startswith(b"\xff\xd8\xff"):
        raise ValidationError("Invalid JPEG file signature")

    if ext == "png" and not header.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValidationError("Invalid PNG file signature")


def upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f"kyc_documents/{instance.merchant_id}/{uuid.uuid4()}{ext}"


validators = [validate_file_size, validate_document_type, validate_document_signature]

# ================== MODELS ==================

class Merchant(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, default="")

    def __str__(self):
        return self.email


class Notification(models.Model):
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    submission = models.ForeignKey(
        "KYCSubmission",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    event_type = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]


class KYCSubmissionQuerySet(models.QuerySet):
    def reviewer_queue(self):
        return self.filter(status__in=REVIEWER_QUEUE_STATUSES).order_by("created_at")


class KYCSubmission(models.Model):
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="submissions",
    )

    business_name = models.CharField(max_length=255)
    business_type = models.CharField(max_length=100)
    monthly_volume = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    pan_document = models.FileField(
        upload_to=upload_path,
        validators=validators,
        null=True,
        blank=True,
    )
    aadhaar_document = models.FileField(
        upload_to=upload_path,
        validators=validators,
        null=True,
        blank=True,
    )
    bank_statement = models.FileField(
        upload_to=upload_path,
        validators=validators,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    status_changed_at = models.DateTimeField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = KYCSubmissionQuerySet.as_manager()

    class Meta:
        ordering = ["created_at", "id"]

    # ================== STATE MACHINE ==================

    def can_transition(self, new_status):
        return new_status in ALLOWED_TRANSITIONS.get(self.status, [])

    def missing_documents(self):
        missing = []
        if not self.pan_document:
            missing.append("PAN")
        if not self.aadhaar_document:
            missing.append("Aadhaar")
        if not self.bank_statement:
            missing.append("Bank")
        return missing

    def assign_reviewer(self):
        return

    def transition_to(self, new_status, reason=None):
        if not self.can_transition(new_status):
            allowed_next = ALLOWED_TRANSITIONS.get(self.status, [])
            raise ValueError(
                f"Invalid transition {self.status} → {new_status}. "
                f"Allowed: {allowed_next if allowed_next else 'no further transitions'}"
            )

        if new_status == STATUS_SUBMITTED:
            missing = self.missing_documents()
            if missing:
                raise ValueError(f"Missing docs: {', '.join(missing)}")

        if new_status in (STATUS_REJECTED, STATUS_MORE_INFO_REQUESTED) and not reason:
            raise ValueError("A reason is required for reject/request_info transitions")

        old_status = self.status
        self.status = new_status
        self.status_changed_at = timezone.now()
        self.save(update_fields=["status", "status_changed_at", "updated_at"])

        payload = {"from": old_status, "to": new_status}
        if reason:
            payload["reason"] = reason

        Notification.objects.create(
            merchant=self.merchant,
            submission=self,
            event_type="status_changed",
            payload=payload,
        )

    @property
    def is_at_risk(self):
        if self.status not in AT_RISK_STATUSES:
            return False
        return self.created_at < timezone.now() - timedelta(hours=SLA_AT_RISK_HOURS)

    def __str__(self):
        return f"{self.business_name} ({self.status})"


# Keep backwards compatibility with historical migrations.
def kyc_document_upload_path(instance, filename):
    return upload_path(instance, filename)