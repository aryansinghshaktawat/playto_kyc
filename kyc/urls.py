from rest_framework.routers import DefaultRouter
from .views import KYCSubmissionViewSet

router = DefaultRouter()
# Register the viewset at the root of this included URLconf so that
# including this file at /api/v1/kyc/ exposes the list/create at /api/v1/kyc/
router.register(r"", KYCSubmissionViewSet, basename="kyc")

urlpatterns = router.urls