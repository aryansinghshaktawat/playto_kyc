from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import KYCSubmissionViewSet

router = DefaultRouter()
router.register("kyc", KYCSubmissionViewSet, basename="kyc")

urlpatterns = [
    path("", include(router.urls)),
]
