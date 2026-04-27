import os

from rest_framework import serializers

from kyc.models import KYCSubmission


MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


class KYCSubmissionSerializer(serializers.ModelSerializer):
    """Serializer for KYCSubmission API."""

    is_at_risk = serializers.BooleanField(read_only=True)
    merchant = serializers.PrimaryKeyRelatedField(read_only=True)

    pan_document = serializers.FileField(required=False, allow_null=True, allow_empty_file=False)
    aadhaar_document = serializers.FileField(required=False, allow_null=True, allow_empty_file=False)
    bank_statement = serializers.FileField(required=False, allow_null=True, allow_empty_file=False)

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

        current_pos = None
        if hasattr(uploaded_file, "tell") and hasattr(uploaded_file, "seek"):
            try:
                current_pos = uploaded_file.tell()
            except Exception:
                current_pos = None

        header = uploaded_file.read(16)
        if current_pos is not None:
            uploaded_file.seek(current_pos)

        if extension == ".pdf" and not header.startswith(b"%PDF-"):
            raise serializers.ValidationError(
                f"{field_label}: invalid PDF file signature."
            )

        if extension in {".jpg", ".jpeg"} and not header.startswith(b"\xff\xd8\xff"):
            raise serializers.ValidationError(
                f"{field_label}: invalid JPEG file signature."
            )

        if extension == ".png" and not header.startswith(b"\x89PNG\r\n\x1a\n"):
            raise serializers.ValidationError(
                f"{field_label}: invalid PNG file signature."
            )

        return uploaded_file

    def validate_pan_document(self, value):
        return self._validate_upload(value, "pan_document")

    def validate_aadhaar_document(self, value):
        return self._validate_upload(value, "aadhaar_document")

    def validate_bank_statement(self, value):
        return self._validate_upload(value, "bank_statement")

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get("request") if hasattr(self, "context") else None

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

        representation["pan_document"] = _url(getattr(instance, "pan_document", None))
        representation["aadhaar_document"] = _url(getattr(instance, "aadhaar_document", None))
        representation["bank_statement"] = _url(getattr(instance, "bank_statement", None))
        return representation

    def validate(self, attrs):
        if self.instance and "merchant" in attrs:
            raise serializers.ValidationError("Merchant cannot be changed once set.")
        return attrs