from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from kyc.models import (
    KYCSubmission,
    Merchant,
    STATUS_APPROVED,
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    STATUS_UNDER_REVIEW,
)


class KYCSubmissionStateMachineTests(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="Test Merchant",
            email="merchant@example.com",
            phone="9999999999",
        )

    def test_valid_state_transition_submitted_to_under_review(self):
        submission = KYCSubmission.objects.create(
            merchant=self.merchant,
            business_name="Acme Pvt Ltd",
            business_type="Ecommerce",
            monthly_volume=1000,
            status=STATUS_SUBMITTED,
        )

        submission.transition_to(STATUS_UNDER_REVIEW)
        submission.refresh_from_db()

        self.assertEqual(submission.status, STATUS_UNDER_REVIEW)

    def test_invalid_transition_draft_to_approved_should_fail(self):
        submission = KYCSubmission.objects.create(
            merchant=self.merchant,
            business_name="Acme Pvt Ltd",
            business_type="Ecommerce",
            monthly_volume=1000,
            status=STATUS_DRAFT,
        )

        with self.assertRaises(ValueError):
            submission.transition_to(STATUS_APPROVED)


class KYCSubmissionAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.client = APIClient()

        self.reviewer = User.objects.create_user(
            username="reviewer1",
            email="reviewer@example.com",
            password="password123",
            is_staff=True,
        )

        self.merchant_user = User.objects.create_user(
            username="merchant1",
            email="merchant1@example.com",
            password="password123",
            is_staff=False,
        )

        self.merchant = Merchant.objects.create(
            name="Merchant One",
            email="merchant1@example.com",
            phone="9999999999",
        )

    def test_file_validation_rejects_invalid_file_type(self):
        self.client.force_authenticate(user=self.merchant_user)
        bad_file = SimpleUploadedFile("malicious.txt", b"hello", content_type="text/plain")

        payload = {
            "business_name": "Bad File Biz",
            "business_type": "Retail",
            "monthly_volume": "1000.00",
            "pan_document": bad_file,
        }

        response = self.client.post(reverse("kyc-list"), payload, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_permission_merchant_cannot_approve(self):
        submission = KYCSubmission.objects.create(
            merchant=self.merchant,
            business_name="Needs Approval",
            business_type="SaaS",
            monthly_volume="5000.00",
            status=STATUS_UNDER_REVIEW,
        )

        self.client.force_authenticate(user=self.merchant_user)
        response = self.client.post(reverse("kyc-approve", kwargs={"pk": submission.pk}))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_auto_assigns_merchant_from_logged_in_user(self):
        self.client.force_authenticate(user=self.merchant_user)

        payload = {
            "business_name": "Auto Assign Biz",
            "business_type": "Services",
            "monthly_volume": "2500.00",
        }
        response = self.client.post(reverse("kyc-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = KYCSubmission.objects.get(pk=response.data["id"])
        self.assertEqual(created.merchant.email, self.merchant_user.email)

    def test_reviewer_can_move_submitted_to_under_review(self):
        submission = KYCSubmission.objects.create(
            merchant=self.merchant,
            business_name="Submitted Biz",
            business_type="SaaS",
            monthly_volume="4200.00",
            status=STATUS_SUBMITTED,
        )

        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(
            reverse("kyc-start-review", kwargs={"pk": submission.pk}),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        submission.refresh_from_db()
        self.assertEqual(submission.status, STATUS_UNDER_REVIEW)

    def test_reviewer_metrics_endpoint(self):
        KYCSubmission.objects.create(
            merchant=self.merchant,
            business_name="Queue One",
            business_type="Agency",
            monthly_volume="1000.00",
            status=STATUS_SUBMITTED,
        )
        KYCSubmission.objects.create(
            merchant=self.merchant,
            business_name="Queue Two",
            business_type="Services",
            monthly_volume="2000.00",
            status=STATUS_UNDER_REVIEW,
        )

        self.client.force_authenticate(user=self.reviewer)
        response = self.client.get(reverse("kyc-reviewer-metrics"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("queue_count", response.data)
        self.assertIn("avg_time_in_queue_hours", response.data)
        self.assertIn("approval_rate_7d", response.data)
