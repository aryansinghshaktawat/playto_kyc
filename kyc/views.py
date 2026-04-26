from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .models import KYCSubmission, Merchant, STATUS_MORE_INFO_REQUESTED, STATUS_SUBMITTED
from .serializers import KYCSubmissionSerializer


class KYCSubmissionViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing KYC submissions.

    Status changes are delegated to the model's state machine so transition
    rules stay centralized and consistent across the application.
    """

    queryset = KYCSubmission.objects.all()
    serializer_class = KYCSubmissionSerializer
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def _get_request_merchant(self):
        try:
            return Merchant.objects.get(email=self.request.user.email)
        except Merchant.DoesNotExist as exc:
            raise PermissionDenied(
                "No Merchant record matches the authenticated user."
            ) from exc

    def _raise_drf_validation_error(self, exc):
        if hasattr(exc, "message_dict"):
            raise ValidationError(exc.message_dict)

        raise ValidationError({"detail": exc.messages})

    def get_queryset(self):
        """
        Reviewers can inspect every submission. Merchants are restricted to
        submissions that match their authenticated email address.
        """
        queryset = KYCSubmission.objects.select_related("merchant")

        if self.request.user.is_staff:
            if self.request.query_params.get("queue") in {"1", "true", "review"}:
                return queryset.reviewer_queue()
            return queryset

        return queryset.filter(merchant__email=self.request.user.email)

    def perform_create(self, serializer):
        """
        Prevent merchants from creating submissions for another merchant by
        binding the record to the authenticated merchant email.
        """
        if self.request.user.is_staff:
            serializer.save()
            return

        serializer.save(merchant=self._get_request_merchant())

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                self.perform_create(serializer)
        except DjangoValidationError as exc:
            self._raise_drf_validation_error(exc)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def _validate_status_actor_permissions(self, current_status, new_status):
        """
        Merchants can only submit or resubmit documents.
        Reviewer-only decisions stay on staff accounts.
        """
        if self.request.user.is_staff or new_status is None:
            return

        allowed_transitions = {
            (None, STATUS_SUBMITTED),
            ("draft", STATUS_SUBMITTED),
            (STATUS_MORE_INFO_REQUESTED, STATUS_SUBMITTED),
        }
        if (current_status, new_status) not in allowed_transitions:
            raise ValidationError(
                {
                    "status": [
                        "Merchants can only submit or resubmit their own KYC submissions."
                    ]
                }
            )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        new_status = request.data.get("status")
        self._validate_status_actor_permissions(instance.status, new_status)

        data = request.data.copy()
        if "status" in data:
            data.pop("status")

        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                if request.user.is_staff:
                    serializer.save()
                else:
                    serializer.save(merchant=self._get_request_merchant())
                if new_status is not None:
                    instance.transition_to(new_status)
        except DjangoValidationError as exc:
            self._raise_drf_validation_error(exc)
        except ValueError as exc:
            raise ValidationError({"status": [str(exc)]})

        instance.refresh_from_db()
        response_serializer = self.get_serializer(instance)
        return Response(response_serializer.data)
