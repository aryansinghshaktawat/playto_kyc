from rest_framework.routers import DefaultRouter

from .views import KYCSubmissionViewSet

router = DefaultRouter()
router.register("kyc", KYCSubmissionViewSet, basename="kyc-submission")

urlpatterns = router.urls
