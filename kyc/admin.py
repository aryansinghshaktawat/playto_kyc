from django.contrib import admin

from .models import KYCSubmission, Merchant, NotificationLog

admin.site.register(Merchant)
admin.site.register(KYCSubmission)
admin.site.register(NotificationLog)
