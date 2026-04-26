from django.test import TestCase

from .models import KYCSubmission, Merchant, STATUS_APPROVED


class KYCSubmissionStateMachineTests(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="Test Merchant",
            email="merchant@example.com",
            phone="9999999999",
        )

    def test_illegal_transition_raises_value_error(self):
        submission = KYCSubmission.objects.create(
            merchant=self.merchant,
            business_name="Acme Pvt Ltd",
            business_type="Ecommerce",
            monthly_volume=1000,
        )

        with self.assertRaisesMessage(
            ValueError,
            "Invalid status transition from 'draft' to 'approved'.",
        ):
            submission.transition_to(STATUS_APPROVED)
