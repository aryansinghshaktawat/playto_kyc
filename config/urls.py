from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from kyc.views import home

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('api/v1/', include('kyc.urls')),
    path('api-auth/', include('rest_framework.urls')),  # 👈 IMPORTANT
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)