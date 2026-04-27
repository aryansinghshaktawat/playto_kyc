import logging
from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied

from kyc.models import KYCSubmission, Merchant
from kyc.serializers import KYCSubmissionSerializer


logger = logging.getLogger(__name__)


def home(request):
    return HttpResponse("API WORKING")


class KYCSubmissionViewSet(viewsets.ModelViewSet):

    queryset = KYCSubmission.objects.select_related("merchant")
    serializer_class = KYCSubmissionSerializer

    # ======================
    # PERMISSIONS
    # ======================
    def get_permissions(self):
        if self.action in [
            "start_review",
            "approve",
            "reject",
            "request_info",
            "reviewer_queue",
            "at_risk",
            "reviewer_metrics",
        ]:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    # ======================
    # QUERYSET
    # ======================
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return self.queryset
        return self.queryset.filter(merchant__email=user.email)

    # ======================
    # MERCHANT
    # ======================
    def _get_merchant(self):
        user = self.request.user
        if not user.email:
            raise ValidationError("Authenticated user must have an email to submit KYC.")

        merchant, _ = Merchant.objects.get_or_create(
            email=user.email,
            defaults={"name": user.username or user.email, "phone": "9999999999"}
        )
        return merchant

    # ======================
    # CREATE
    # ======================
    def perform_create(self, serializer):
        serializer.save(merchant=self._get_merchant())

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            with transaction.atomic():
                self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as exc:
            return Response({"error": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError as exc:
            logger.exception("Django validation error while creating submission")
            detail = getattr(exc, "message_dict", exc.messages)
            return Response({"error": detail}, status=status.HTTP_400_BAD_REQUEST)
        except OSError as exc:
            logger.exception("Storage error while creating submission")
            return Response(
                {
                    "error": "File upload/storage failed.",
                    "detail": str(exc),
                    "hint": "Use cloud storage (S3/R2/GCS) in production.",
                },
                status=status.HTTP_507_INSUFFICIENT_STORAGE,
            )
        except Exception as exc:
            logger.exception("Unexpected error while creating submission")
            return Response(
                {"error": "Unexpected server error.", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        try:
            serializer.is_valid(raise_exception=True)
            with transaction.atomic():
                serializer.save(merchant=self._get_merchant() if not request.user.is_staff else instance.merchant)
            return Response(self.get_serializer(instance).data, status=status.HTTP_200_OK)
        except ValidationError as exc:
            return Response({"error": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        except OSError as exc:
            logger.exception("Storage error while updating submission")
            return Response(
                {"error": "File upload/storage failed.", "detail": str(exc)},
                status=status.HTTP_507_INSUFFICIENT_STORAGE,
            )
        except Exception as exc:
            logger.exception("Unexpected error while updating submission")
            return Response(
                {"error": "Unexpected server error.", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _transition(self, request, pk, new_status):
        obj = self.get_object()
        reason = request.data.get("reason") if hasattr(request, "data") else None
        try:
            with transaction.atomic():
                obj.transition_to(new_status, reason=reason)
            return Response(self.get_serializer(obj).data, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as exc:
            return Response({"error": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Unexpected error while transitioning submission")
            return Response(
                {"error": "Unexpected server error.", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        requested_status = request.data.get("status")
        if not requested_status:
            return Response(
                {"error": "Missing required field: status."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        requested_status = str(requested_status).strip().lower()
        allowed_statuses = {
            "submitted",
            "under_review",
            "approved",
            "rejected",
            "more_info_requested",
        }
        if requested_status not in allowed_statuses:
            return Response(
                {
                    "error": "Invalid target status.",
                    "allowed_statuses": sorted(allowed_statuses),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        reviewer_statuses = {"under_review", "approved", "rejected", "more_info_requested"}
        if requested_status in reviewer_statuses and not request.user.is_staff:
            raise PermissionDenied("Only reviewers can perform this transition.")

        if requested_status == "submitted" and request.user.is_staff:
            raise PermissionDenied("Reviewers cannot submit merchant KYC records.")

        return self._transition(request, pk, requested_status)

    # ======================
    # SUBMIT
    # ======================
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        # Keep this endpoint merchant-accessible.
        if request.user.is_staff:
            raise PermissionDenied("Reviewers cannot use submit endpoint.")
        return self._transition(request, pk, "submitted")

    # ======================
    # APPROVE
    # ======================
    @action(detail=True, methods=["post"])
    def start_review(self, request, pk=None):
        return self._transition(request, pk, "under_review")

    # ======================
    # APPROVE
    # ======================
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._transition(request, pk, "approved")

    # ======================
    # REJECT
    # ======================
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._transition(request, pk, "rejected")

    # ======================
    # NEED MORE INFO
    # ======================
    @action(detail=True, methods=["post"])
    def request_info(self, request, pk=None):
        return self._transition(request, pk, "more_info_requested")

    # ======================
    # REVIEWER QUEUE
    # ======================
    @action(detail=False, methods=["get"])
    def reviewer_queue(self, request):
        qs = KYCSubmission.objects.reviewer_queue()
        return Response(self.get_serializer(qs, many=True).data)

    # ======================
    # SLA
    # ======================
    @action(detail=False, methods=["get"])
    def at_risk(self, request):
        cutoff = timezone.now() - timedelta(hours=24)
        qs = self.get_queryset().filter(
            status__in=["submitted", "under_review"],
            created_at__lt=cutoff,
        )
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def reviewer_metrics(self, request):
        now = timezone.now()
        queue_qs = KYCSubmission.objects.reviewer_queue()
        queue_count = queue_qs.count()

        avg_time_in_queue_hours = 0.0
        if queue_count:
            total_seconds = sum(
                (now - submission.created_at).total_seconds() for submission in queue_qs
            )
            avg_time_in_queue_hours = round(total_seconds / queue_count / 3600, 2)

        since = now - timedelta(days=7)
        recent = KYCSubmission.objects.filter(created_at__gte=since)
        recent_total = recent.count()
        recent_approved = recent.filter(status="approved").count()
        approval_rate_7d = (
            round((recent_approved / recent_total) * 100, 2) if recent_total else 0.0
        )

        return Response(
            {
                "queue_count": queue_count,
                "avg_time_in_queue_hours": avg_time_in_queue_hours,
                "approval_rate_7d": approval_rate_7d,
            },
            status=status.HTTP_200_OK,
        )