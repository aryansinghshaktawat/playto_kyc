import os
from rest_framework import serializers
from kyc.models import KYCSubmission

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


class KYCSubmissionSerializer(serializers.ModelSerializer):
    is_at_risk = serializers.BooleanField(read_only=True)

    # 👇 IMPORTANT FIX
    merchant = serializers.PrimaryKeyRelatedField(read_only=True)

    pan_document = serializers.FileField(required=False, allow_null=True, allow_empty_file=True)
    aadhaar_document = serializers.FileField(required=False, allow_null=True, allow_empty_file=True)
    bank_statement = serializers.FileField(required=False, allow_null=True, allow_empty_file=True)

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
            "status_changed_at",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "merchant",
            "status",
            "is_at_risk",
            "status_changed_at",
            "created_at",
            "updated_at",
        ]

        # 🔥 CRITICAL FIX
        extra_kwargs = {
            "merchant": {"required": False}
        }

    # ======================
    # FILE VALIDATION
    # ======================

    def _validate_upload(self, uploaded_file, field_label):
        if uploaded_file is None:
            return uploaded_file

        extension = os.path.splitext(uploaded_file.name)[1].lower()

        if extension not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise serializers.ValidationError(
                f"{field_label}: unsupported file type. Allowed: {allowed}."
            )

        if uploaded_file.size > MAX_UPLOAD_SIZE:
            raise serializers.ValidationError(
                f"{field_label}: file size must not exceed 5MB."
            )

        return uploaded_file

    def validate_pan_document(self, value):
        return self._validate_upload(value, "pan_document")

    def validate_aadhaar_document(self, value):
        return self._validate_upload(value, "aadhaar_document")

    def validate_bank_statement(self, value):
        return self._validate_upload(value, "bank_statement")

    # ======================
    # SAFE CREATE (IMPORTANT)
    # ======================

    def create(self, validated_data):
        """
        Ensure merchant is always attached (fallback safety).
        """
        request = self.context.get("request")

        if request and request.user.is_authenticated:
            validated_data["merchant"] = getattr(request.user, "merchant", None)

        return super().create(validated_data)

    # ======================
    # RESPONSE FORMAT
    # ======================

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get("request")

        def _url(file_value):
            if not file_value:
                return None
            try:
                relative_url = file_value.url
            except Exception:
                return None
            if request:
                return request.build_absolute_uri(relative_url)
            return relative_url

        representation["pan_document"] = _url(instance.pan_document)
        representation["aadhaar_document"] = _url(instance.aadhaar_document)
        representation["bank_statement"] = _url(instance.bank_statement)

        return representation

    # ======================
    # VALIDATION
    # ======================

    def validate(self, attrs):
        if self.instance and "merchant" in attrs:
            raise serializers.ValidationError("Merchant cannot be changed once set.")
        return attrs