import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import HttpResponse

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
        if self.action in ["transition", "approve", "reject", "request_info", "reviewer_queue"]:
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
        try:
            with transaction.atomic():
                obj.transition_to(new_status)
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
        qs = self.get_queryset()
        qs = [x for x in qs if x.is_at_risk]
        return Response(self.get_serializer(qs, many=True).data)