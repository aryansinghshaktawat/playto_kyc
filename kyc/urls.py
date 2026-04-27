from rest_framework.routers import DefaultRouter
from kyc.views import KYCSubmissionViewSet

router = DefaultRouter()
# Register at the router root so including this module at /api/v1/kyc/ exposes
# list/create at /api/v1/kyc/ and detail at /api/v1/kyc/<pk>/
router.register(r"kyc", KYCSubmissionViewSet, basename="kyc")

urlpatterns = router.urls