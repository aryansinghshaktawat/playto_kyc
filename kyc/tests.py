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
    STATUS_MORE_INFO_REQUESTED,
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

        self.other_merchant_user = User.objects.create_user(
            username="merchant2",
            email="merchant2@example.com",
            password="password123",
            is_staff=False,
        )

        self.other_merchant = Merchant.objects.create(
            name="Merchant Two",
            email="merchant2@example.com",
            phone="9999999998",
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

    def test_file_validation_rejects_invalid_pdf_signature(self):
        self.client.force_authenticate(user=self.merchant_user)
        fake_pdf = SimpleUploadedFile(
            "tampered.pdf",
            b"NOT_A_PDF_FILE",
            content_type="application/pdf",
        )

        payload = {
            "business_name": "Tampered Doc Biz",
            "business_type": "Retail",
            "monthly_volume": "1000.00",
            "pan_document": fake_pdf,
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

    def test_submit_without_documents_returns_400(self):
        submission = KYCSubmission.objects.create(
            merchant=self.merchant,
            business_name="No Docs Biz",
            business_type="Agency",
            monthly_volume="1900.00",
            status=STATUS_DRAFT,
        )

        self.client.force_authenticate(user=self.merchant_user)
        response = self.client.post(
            reverse("kyc-transition", kwargs={"pk": submission.pk}),
            {"status": "submitted"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Missing docs", str(response.data.get("error", "")))

    def test_reapprove_approved_submission_returns_400(self):
        submission = KYCSubmission.objects.create(
            merchant=self.merchant,
            business_name="Approved Biz",
            business_type="Agency",
            monthly_volume="3000.00",
            status=STATUS_APPROVED,
        )

        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(
            reverse("kyc-transition", kwargs={"pk": submission.pk}),
            {"status": "approved", "reason": "Already checked"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid transition", str(response.data.get("error", "")))

    def test_transition_invalid_status_returns_400(self):
        submission = KYCSubmission.objects.create(
            merchant=self.merchant,
            business_name="Transition Biz",
            business_type="Agency",
            monthly_volume="3000.00",
            status=STATUS_SUBMITTED,
        )

        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(
            reverse("kyc-transition", kwargs={"pk": submission.pk}),
            {"status": "archived"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("allowed_statuses", response.data)

    def test_transition_request_info_requires_reason(self):
        submission = KYCSubmission.objects.create(
            merchant=self.merchant,
            business_name="Need Clarification Biz",
            business_type="Agency",
            monthly_volume="3000.00",
            status=STATUS_UNDER_REVIEW,
        )

        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(
            reverse("kyc-transition", kwargs={"pk": submission.pk}),
            {"status": STATUS_MORE_INFO_REQUESTED},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", str(response.data.get("error", "")).lower())

    def test_merchant_cannot_view_other_merchant_submission(self):
        other_submission = KYCSubmission.objects.create(
            merchant=self.other_merchant,
            business_name="Other Merchant Biz",
            business_type="SaaS",
            monthly_volume="4000.00",
            status=STATUS_DRAFT,
        )

        self.client.force_authenticate(user=self.merchant_user)
        response = self.client.get(reverse("kyc-detail", kwargs={"pk": other_submission.pk}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
