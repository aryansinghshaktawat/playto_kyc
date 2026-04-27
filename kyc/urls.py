from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import KYCSubmissionViewSet

router = DefaultRouter()
router.register(r'kyc', KYCSubmissionViewSet, basename='kyc')

urlpatterns = [
    path('', include(router.urls)),
]