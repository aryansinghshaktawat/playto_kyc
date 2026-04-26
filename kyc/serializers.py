from rest_framework import serializers

from .models import KYCSubmission


class KYCSubmissionSerializer(serializers.ModelSerializer):
    """
    Serializer for reading and writing KYC submission records.

    File validation is enforced by the model field validators, and DRF will
    surface those errors as structured JSON responses.
    """
    is_at_risk = serializers.BooleanField(read_only=True)

    class Meta:
        model = KYCSubmission
        fields = [
            "id",
            "merchant",
            "business_name",
            "business_type",
            "monthly_volume",
            "pan_document",
            "aadhaar_document",
            "bank_statement",
            "status",
            "is_at_risk",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_at_risk", "created_at", "updated_at"]

    def get_fields(self):
        """
        Merchants should not be able to reassign submissions to another merchant.
        """
        fields = super().get_fields()
        request = self.context.get("request")

        if request and request.user.is_authenticated and not request.user.is_staff:
            fields["merchant"].read_only = True

        return fields

    def validate(self, attrs):
        """
        Prevent moving an existing submission to another merchant through the API.
        """
        if self.instance and "merchant" in attrs and attrs["merchant"] != self.instance.merchant:
            raise serializers.ValidationError("Merchant cannot be changed once set.")

        return attrs
