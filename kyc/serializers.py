from rest_framework import serializers
from .models import KYCSubmission


class KYCSubmissionSerializer(serializers.ModelSerializer):
    """
    Serializer for reading and writing KYC submission records.

    - Ensures file URLs are absolute (important for production)
    - Prevents merchant reassignment
    - Respects role-based field access
    """

    is_at_risk = serializers.BooleanField(read_only=True)

    # Convert file fields to full URLs
    pan_document = serializers.SerializerMethodField()
    aadhaar_document = serializers.SerializerMethodField()
    bank_statement = serializers.SerializerMethodField()

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

    # ======================
    # FILE URL HANDLING
    # ======================

    def _build_file_url(self, file_field):
        request = self.context.get("request")
        if file_field and hasattr(file_field, "url"):
            if request:
                return request.build_absolute_uri(file_field.url)
            return file_field.url
        return None

    def get_pan_document(self, obj):
        return self._build_file_url(obj.pan_document)

    def get_aadhaar_document(self, obj):
        return self._build_file_url(obj.aadhaar_document)

    def get_bank_statement(self, obj):
        return self._build_file_url(obj.bank_statement)

    # ======================
    # FIELD CONTROL
    # ======================

    def get_fields(self):
        """
        Merchants should not be able to reassign submissions to another merchant.
        """
        fields = super().get_fields()
        request = self.context.get("request")

        # If non-staff authenticated users are making the request, merchant
        # should be read-only to avoid reassignment. Allow staff to set it.
        if request and getattr(request, "user", None) is not None:
            try:
                is_staff = request.user.is_staff
            except Exception:
                is_staff = False

            if not is_staff:
                if "merchant" in fields:
                    fields["merchant"].read_only = True

        return fields

    # ======================
    # VALIDATION
    # ======================

    def validate(self, attrs):
        """
        Prevent moving an existing submission to another merchant through the API.
        """
        if self.instance and "merchant" in attrs and attrs["merchant"] != self.instance.merchant:
            raise serializers.ValidationError("Merchant cannot be changed once set.")

        return attrs