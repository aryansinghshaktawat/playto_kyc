from django.contrib import admin
from django.urls import path, include
from kyc.views import home

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("api/v1/", include("kyc.urls")),
]
