from datetime import timedelta
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APIClient

from kyc.models import (
    KYCSubmission,
    Merchant,
    STATUS_SUBMITTED,
    STATUS_UNDER_REVIEW,
    STATUS_DRAFT,
)

User = get_user_model()

class KYCExtendedCoverageTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.reviewer = User.objects.create_user(
            username="reviewer_ext",
            email="reviewer_ext@example.com",
            password="password123",
            is_staff=True,
            is_superuser=True,
        )

        self.merchant_user = User.objects.create_user(
            username="merchant_ext",
            email="merchant_ext@example.com",
            password="password123",
            is_staff=False,
        )

        self.merchant = Merchant.objects.create(
            name="Merchant Ext",
            email="merchant_ext@example.com",
            phone="9999999999",
        )

    def test_list_submissions_filters_properly(self):
        # Create submission for merchant_ext
        KYCSubmission.objects.create(
            merchant=self.merchant,
            business_name="Ext Biz",
            business_type="LLC",
            monthly_volume="1000",
            status=STATUS_DRAFT,
        )
        
        # Create second merchant and submission
        other_merchant_user = User.objects.create_user(
            username="other2", email="other2@example.com", password="pwd"
        )
        other_merchant = Merchant.objects.create(
            name="Other", email="other2@example.com"
        )
        KYCSubmission.objects.create(
            merchant=other_merchant,
            business_name="Other Biz",
            business_type="LLC",
            monthly_volume="2000",
            status=STATUS_DRAFT,
        )

        # Authenticate as merchant_ext -> should only see 1
        self.client.force_authenticate(user=self.merchant_user)
        response = self.client.get(reverse("kyc-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["business_name"], "Ext Biz")

        # Authenticate as reviewer -> should see both
        self.client.force_authenticate(user=self.reviewer)
        response = self.client.get(reverse("kyc-list"))
        self.assertEqual(len(response.data), 2)

    def test_update_partially(self):
        sub = KYCSubmission.objects.create(
            merchant=self.merchant,
            business_name="Update Biz",
            business_type="LLC",
            monthly_volume="1000",
            status=STATUS_DRAFT,
        )

        self.client.force_authenticate(user=self.merchant_user)
        response = self.client.patch(
            reverse("kyc-detail", kwargs={"pk": sub.pk}),
            {"monthly_volume": "3000.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sub.refresh_from_db()
        self.assertEqual(sub.monthly_volume, 3000.00)

    def test_delete_submission(self):
        sub = KYCSubmission.objects.create(
            merchant=self.merchant,
            business_name="Delete Biz",
            business_type="LLC",
            monthly_volume="1000",
            status=STATUS_DRAFT,
        )
        self.client.force_authenticate(user=self.merchant_user)
        response = self.client.delete(reverse("kyc-detail", kwargs={"pk": sub.pk}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(KYCSubmission.objects.filter(pk=sub.pk).exists())

    def test_at_risk_sla_endpoint(self):
        # Create normal submitted
        KYCSubmission.objects.create(
            merchant=self.merchant,
            business_name="Normal",
            business_type="LLC",
            monthly_volume="1000",
            status=STATUS_SUBMITTED,
        )

        # Create at-risk submitted (older than 24 hours)
        at_risk = KYCSubmission.objects.create(
            merchant=self.merchant,
            business_name="Risk",
            business_type="LLC",
            monthly_volume="1000",
            status=STATUS_SUBMITTED,
        )
        # Manually alter created_at using update
        KYCSubmission.objects.filter(pk=at_risk.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )

        self.client.force_authenticate(user=self.reviewer)
        response = self.client.get(reverse("kyc-at-risk"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Only the older one should be returned
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["business_name"], "Risk")

    def test_reviewer_queue_endpoint(self):
        KYCSubmission.objects.create(
             merchant=self.merchant, business_name="Q1", business_type="LLC", monthly_volume="100", status=STATUS_SUBMITTED
        )
        KYCSubmission.objects.create(
             merchant=self.merchant, business_name="Q2", business_type="LLC", monthly_volume="100", status=STATUS_UNDER_REVIEW
        )
        KYCSubmission.objects.create(
             merchant=self.merchant, business_name="Q3", business_type="LLC", monthly_volume="100", status=STATUS_DRAFT
        )

        self.client.force_authenticate(user=self.reviewer)
        response = self.client.get(reverse("kyc-reviewer-queue"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # Draft shouldn't be here

    def test_large_file_validation(self):
        self.client.force_authenticate(user=self.merchant_user)
        # Create a dummy payload larger than 5MB
        large_content = b"0" * (5 * 1024 * 1024 + 1024)  # 5MB + 1KB
        large_file = SimpleUploadedFile("big.pdf", large_content, content_type="application/pdf")
        
        # For the signature to pass, it must start with %PDF-
        large_content_valid_sig = b"%PDF-" + large_content
        large_file_sig = SimpleUploadedFile("big.pdf", large_content_valid_sig, content_type="application/pdf")

        payload = {
            "business_name": "Large File Biz",
            "business_type": "LLC",
            "monthly_volume": "1000.00",
            "pan_document": large_file_sig,
        }

        response = self.client.post(reverse("kyc-list"), payload, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("pan_document", response.data["error"])
        self.assertIn("File must be \u2264 5MB", str(response.data["error"]))
