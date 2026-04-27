from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from kyc.models import KYCSubmission, Merchant, STATUS_DRAFT, STATUS_UNDER_REVIEW


class Command(BaseCommand):
    help = "Seed initial data: 2 merchants and 1 reviewer (admin user)."

    def handle(self, *args, **options):
        User = get_user_model()

        reviewer, reviewer_created = User.objects.get_or_create(
            username="reviewer1",
            defaults={
                "email": "reviewer@example.com",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        reviewer.set_password("password123")
        reviewer.is_staff = True
        reviewer.is_superuser = True
        reviewer.save(update_fields=["password", "is_staff", "is_superuser"])

        merchant_user_1, _ = User.objects.get_or_create(
            username="merchant1",
            defaults={"email": "merchant1@example.com"},
        )
        merchant_user_1.set_password("password123")
        merchant_user_1.is_staff = False
        merchant_user_1.save(update_fields=["password", "is_staff"])

        merchant_user_2, _ = User.objects.get_or_create(
            username="merchant2",
            defaults={"email": "merchant2@example.com"},
        )
        merchant_user_2.set_password("password123")
        merchant_user_2.is_staff = False
        merchant_user_2.save(update_fields=["password", "is_staff"])

        merchant_1, m1_created = Merchant.objects.get_or_create(
            email="merchant1@example.com",
            defaults={"name": "Merchant One", "phone": "9999999991"},
        )
        merchant_2, m2_created = Merchant.objects.get_or_create(
            email="merchant2@example.com",
            defaults={"name": "Merchant Two", "phone": "9999999992"},
        )

        draft_submission, draft_created = KYCSubmission.objects.get_or_create(
            merchant=merchant_1,
            business_name="Merchant One Draft Co",
            defaults={
                "business_type": "Agency",
                "monthly_volume": 3000,
                "status": STATUS_DRAFT,
            },
        )

        review_submission, review_created = KYCSubmission.objects.get_or_create(
            merchant=merchant_2,
            business_name="Merchant Two Review Co",
            defaults={
                "business_type": "Freelancer",
                "monthly_volume": 5000,
                "status": STATUS_UNDER_REVIEW,
            },
        )

        self.stdout.write(self.style.SUCCESS("Seed complete."))
        self.stdout.write(
            f"Reviewer: {reviewer.username} ({'created' if reviewer_created else 'updated'})"
        )
        self.stdout.write(
            f"Merchant 1: {merchant_1.email} ({'created' if m1_created else 'existing'})"
        )
        self.stdout.write(
            f"Merchant 2: {merchant_2.email} ({'created' if m2_created else 'existing'})"
        )
        self.stdout.write(
            f"Draft submission: {draft_submission.business_name} ({'created' if draft_created else 'existing'})"
        )
        self.stdout.write(
            f"Under review submission: {review_submission.business_name} ({'created' if review_created else 'existing'})"
        )
