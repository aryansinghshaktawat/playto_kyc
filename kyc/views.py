import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import HttpResponse

from rest_framework import permissions, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from kyc.models import KYCSubmission, Merchant
from kyc.serializers import KYCSubmissionSerializer


logger = logging.getLogger(__name__)


def home(request):
    return HttpResponse("API WORKING")


class KYCSubmissionViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing KYC submissions.
    """

    queryset = KYCSubmission.objects.all()
    serializer_class = KYCSubmissionSerializer
    parser_classes = [MultiPartParser, FormParser]

    # ======================
    # SERIALIZER CONTEXT
    # ======================
    def get_serializer_context(self):
        return {"request": self.request}

    # ======================
    # PERMISSIONS
    # ======================
    def get_permissions(self):
        # ✅ For testing (change later for production)
        # In production, prefer IsAuthenticated and assign merchant from auth user.
        return [permissions.AllowAny()]

    # ======================
    # SAFE MERCHANT FETCH
    # ======================
    def _get_request_merchant(self):
        if not self.request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        try:
            return Merchant.objects.get(email=self.request.user.email)
        except Merchant.DoesNotExist:
            raise PermissionDenied("Merchant not found for this user.")

    # ======================
    # ERROR HANDLER
    # ======================
    def _raise_drf_validation_error(self, exc):
        if hasattr(exc, "message_dict"):
            raise ValidationError(exc.message_dict)
        raise ValidationError(exc.messages)

    # ======================
    # QUERYSET CONTROL
    # ======================
    def get_queryset(self):
        queryset = KYCSubmission.objects.select_related("merchant")

        if not self.request.user.is_authenticated:
            return queryset

        if self.request.user.is_staff:
            return queryset

        return queryset.filter(merchant__email=self.request.user.email)

    # ======================
    # CREATE
    # ======================
    def perform_create(self, serializer):
        # Safe fallback for unauthenticated submissions (temporary testing mode).
        merchant = None
        if self.request.user.is_authenticated:
            try:
                merchant = self._get_request_merchant()
            except PermissionDenied:
                merchant = None

        if merchant is None:
            merchant = Merchant.objects.order_by("id").first()

        if merchant is None:
            raise ValidationError(
                {
                    "merchant": (
                        "No merchant available for assignment. "
                        "Create at least one Merchant record first."
                    )
                }
            )

        serializer.save(merchant=merchant)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)

            with transaction.atomic():
                self.perform_create(serializer)

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as exc:
            # DRF validation errors (clean JSON response)
            return Response({"error": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError as exc:
            self._raise_drf_validation_error(exc)
        except OSError as exc:
            # Example: disk full, storage backend unavailable, write permission issues.
            logger.exception("File storage error while creating KYC submission")
            return Response(
                {
                    "error": "File upload/storage failed.",
                    "detail": str(exc),
                    "hint": (
                        "For Render/production, prefer cloud object storage "
                        "(S3/R2/GCS) instead of relying on ephemeral local disk."
                    ),
                },
                status=status.HTTP_507_INSUFFICIENT_STORAGE,
            )
        except Exception as exc:
            logger.exception("Unexpected error while creating KYC submission")
            return Response(
                {"error": "Unexpected server error.", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ======================
    # UPDATE + STATUS TRANSITION
    # ======================
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        new_status = request.data.get("status")

        data = request.data.copy()
        if "status" in data:
            data.pop("status")

        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                # ✅ safe merchant handling
                if request.user.is_authenticated:
                    serializer.save(merchant=self._get_request_merchant())
                else:
                    fallback_merchant = Merchant.objects.order_by("id").first()
                    if fallback_merchant is None:
                        raise ValidationError(
                            {
                                "merchant": (
                                    "No merchant available for assignment. "
                                    "Create at least one Merchant record first."
                                )
                            }
                        )
                    serializer.save(merchant=fallback_merchant)

                # ✅ status transition logic
                if new_status is not None:
                    instance.transition_to(new_status)

        except DjangoValidationError as exc:
            self._raise_drf_validation_error(exc)
        except ValueError as exc:
            raise ValidationError(str(exc))
        except OSError as exc:
            logger.exception("File storage error while updating KYC submission")
            raise ValidationError(
                {
                    "storage": (
                        "File upload/storage failed while updating submission. "
                        f"Detail: {exc}"
                    )
                }
            )

        instance.refresh_from_db()
        return Response(self.get_serializer(instance).data)