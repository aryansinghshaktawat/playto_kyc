from django.db import transaction
from django.http import HttpResponse

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied

from kyc.models import KYCSubmission, Merchant
from kyc.serializers import KYCSubmissionSerializer


def home(request):
    return HttpResponse("API WORKING")


class KYCSubmissionViewSet(viewsets.ModelViewSet):

    queryset = KYCSubmission.objects.select_related("merchant", "reviewer")
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
        merchant, _ = Merchant.objects.get_or_create(
            email=user.email,
            defaults={"name": user.username}
        )
        return merchant

    # ======================
    # CREATE
    # ======================
    def perform_create(self, serializer):
        serializer.save(merchant=self._get_merchant())

    # ======================
    # SUBMIT
    # ======================
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        obj = self.get_object()
        try:
            obj.transition_to("submitted")
        except ValueError as e:
            raise ValidationError(str(e))
        return Response(self.get_serializer(obj).data)

    # ======================
    # APPROVE
    # ======================
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        obj = self.get_object()
        obj.transition_to("approved")
        return Response(self.get_serializer(obj).data)

    # ======================
    # REJECT
    # ======================
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        obj = self.get_object()
        obj.transition_to("rejected")
        return Response(self.get_serializer(obj).data)

    # ======================
    # NEED MORE INFO
    # ======================
    @action(detail=True, methods=["post"])
    def request_info(self, request, pk=None):
        obj = self.get_object()
        obj.transition_to("more_info_requested")
        return Response(self.get_serializer(obj).data)

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