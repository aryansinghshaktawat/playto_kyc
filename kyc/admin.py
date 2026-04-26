from django.contrib import admin

from .models import KYCSubmission, Merchant, Notification

admin.site.register(Merchant)
admin.site.register(KYCSubmission)
admin.site.register(Notification)
