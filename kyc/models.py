import os
import uuid
from datetime import timedelta

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


def upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f"kyc_documents/{instance.merchant_id}/{uuid.uuid4()}{ext}"


validators = [validate_file_size, validate_document_type]

# ================== MODELS ==================

class Merchant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.email


class Notification(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    submission = models.ForeignKey("KYCSubmission", on_delete=models.CASCADE)
    event_type = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)


class KYCSubmissionQuerySet(models.QuerySet):
    def reviewer_queue(self):
        return self.filter(status__in=REVIEWER_QUEUE_STATUSES).order_by("created_at")


class KYCSubmission(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    reviewer = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    business_name = models.CharField(max_length=255)
    business_type = models.CharField(max_length=100)
    monthly_volume = models.DecimalField(max_digits=12, decimal_places=2)

    pan_document = models.FileField(upload_to=upload_path, validators=validators, null=True, blank=True)
    aadhaar_document = models.FileField(upload_to=upload_path, validators=validators, null=True, blank=True)
    bank_statement = models.FileField(upload_to=upload_path, validators=validators, null=True, blank=True)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    status_changed_at = models.DateTimeField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = KYCSubmissionQuerySet.as_manager()

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
        reviewer = User.objects.filter(is_staff=True).first()
        if reviewer:
            self.reviewer = reviewer

    def transition_to(self, new_status):

        if not self.can_transition(new_status):
            raise ValueError(f"Invalid transition {self.status} → {new_status}")

        if new_status == STATUS_SUBMITTED:
            missing = self.missing_documents()
            if missing:
                raise ValueError(f"Missing docs: {', '.join(missing)}")
            self.assign_reviewer()

        old_status = self.status
        self.status = new_status
        self.status_changed_at = timezone.now()
        self.save()

        Notification.objects.create(
            merchant=self.merchant,
            submission=self,
            event_type="status_changed",
            payload={"from": old_status, "to": new_status},
        )

    @property
    def is_at_risk(self):
        if self.status not in AT_RISK_STATUSES:
            return False
        return self.created_at < timezone.now() - timedelta(hours=SLA_AT_RISK_HOURS)

    def __str__(self):
        return f"{self.business_name} ({self.status})"