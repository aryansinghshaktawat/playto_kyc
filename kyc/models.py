from datetime import timedelta
import os

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB
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
    STATUS_UNDER_REVIEW: [
        STATUS_APPROVED,
        STATUS_REJECTED,
        STATUS_MORE_INFO_REQUESTED,
    ],
    STATUS_MORE_INFO_REQUESTED: [STATUS_SUBMITTED],
    STATUS_APPROVED: [],
    STATUS_REJECTED: [],
}
SLA_AT_RISK_HOURS = 24
REVIEWER_QUEUE_STATUSES = [STATUS_SUBMITTED, STATUS_UNDER_REVIEW]
AT_RISK_STATUSES = [STATUS_SUBMITTED, STATUS_UNDER_REVIEW]
FILE_SIGNATURES = {
    "pdf": [b"%PDF"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
}


def validate_file_size(uploaded_file):
    """Reject files larger than the supported document upload limit."""
    if uploaded_file.size > MAX_UPLOAD_SIZE:
        raise ValidationError("File size must not exceed 5 MB.")


def validate_document_type(uploaded_file):
    """
    Validate uploads on the backend by checking both extension and file signature.

    This avoids trusting the client to tell us the file type.
    """
    extension = os.path.splitext(uploaded_file.name)[1].lower().lstrip(".")
    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        allowed = ", ".join(ALLOWED_DOCUMENT_EXTENSIONS)
        raise ValidationError(
            f"Unsupported file type. Allowed types are: {allowed}."
        )

    signature = uploaded_file.read(8)
    uploaded_file.seek(0)
    if not any(signature.startswith(prefix) for prefix in FILE_SIGNATURES[extension]):
        raise ValidationError(
            "Uploaded file content does not match an allowed PDF, JPG, JPEG, or PNG file."
        )


def kyc_document_upload_path(instance, filename):
    """Store KYC documents under a predictable merchant-specific path."""
    extension = os.path.splitext(filename)[1].lower()
    safe_name = os.path.splitext(filename)[0].replace(" ", "_")
    return f"kyc_documents/merchant_{instance.merchant_id}/{safe_name}{extension}"


document_validators = [
    validate_file_size,
    validate_document_type,
]


class Merchant(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)

    def __str__(self):
        return self.email


class NotificationLog(models.Model):
    """Audit log for important KYC events such as state changes."""

    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="notification_logs",
    )
    submission = models.ForeignKey(
        "KYCSubmission",
        on_delete=models.CASCADE,
        related_name="notification_logs",
    )
    event_type = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.event_type} for merchant {self.merchant_id}"


class KYCSubmissionQuerySet(models.QuerySet):
    """Query helpers used by merchant and reviewer API flows."""

    def reviewer_queue(self):
        return self.filter(status__in=REVIEWER_QUEUE_STATUSES).order_by("created_at", "id")


class KYCSubmission(models.Model):
    """
    Represents a merchant's KYC submission and enforces its review lifecycle.

    The submission moves through a restricted set of statuses so the system
    cannot skip important review steps or jump back into invalid states.
    """

    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name='submissions',
    )

    business_name = models.CharField(max_length=255)
    business_type = models.CharField(max_length=100)
    monthly_volume = models.FloatField()
    pan_document = models.FileField(
        upload_to=kyc_document_upload_path,
        validators=document_validators,
        blank=True,
        null=True,
    )
    aadhaar_document = models.FileField(
        upload_to=kyc_document_upload_path,
        validators=document_validators,
        blank=True,
        null=True,
    )
    bank_statement = models.FileField(
        upload_to=kyc_document_upload_path,
        validators=document_validators,
        blank=True,
        null=True,
    )

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    status_changed_at = models.DateTimeField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = KYCSubmissionQuerySet.as_manager()

    class Meta:
        ordering = ["created_at", "id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status
        self._allow_status_transition = False

    @property
    def is_at_risk(self):
        """
        Mark pending submissions as at risk once they exceed the 24-hour SLA.
        """
        if self.status not in AT_RISK_STATUSES or not self.created_at:
            return False

        return self.status_changed_at <= timezone.now() - timedelta(hours=SLA_AT_RISK_HOURS)

    def can_transition(self, new_status):
        """
        Return True when moving from the current status to ``new_status`` is allowed.

        This method is the single source of truth for the KYC submission state
        machine, so all transition checks stay inside the model.
        """
        return new_status in ALLOWED_TRANSITIONS.get(self.status, [])

    def clean(self):
        super().clean()

        if self._state.adding and self.status != STATUS_DRAFT:
            raise ValidationError(
                {"status": "New submissions must start in 'draft' status."}
            )

        if not self._state.adding and self.status != self._original_status:
            if not self._allow_status_transition:
                raise ValidationError(
                    {"status": "Status updates must use transition_to()."}
                )

            if self.status not in ALLOWED_TRANSITIONS.get(self._original_status, []):
                raise ValidationError(
                    {
                        "status": (
                            f"Invalid status transition from '{self._original_status}' "
                            f"to '{self.status}'."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        self._original_status = self.status
        self._allow_status_transition = False

    def transition_to(self, new_status):
        """
        Move the submission to a new valid status and persist the change.

        Raises:
            ValueError: If the requested transition is not allowed by the
            state machine.
        """
        if not self.can_transition(new_status):
            raise ValueError(
                f"Invalid status transition from '{self.status}' to '{new_status}'."
            )

        previous_status = self.status
        self.status = new_status
        self._allow_status_transition = True
        self.status_changed_at = timezone.now()
        self.save(update_fields=['status', 'status_changed_at', 'updated_at'])
        NotificationLog.objects.create(
            merchant=self.merchant,
            submission=self,
            event_type="kyc_submission.status_changed",
            payload={
                "old_status": previous_status,
                "new_status": new_status,
                "submission_id": self.pk,
            },
        )

    def __str__(self):
        return f"{self.business_name} - {self.status}"
