from .models import (
    NotificationProvider,
    Integration,
    NotificationTemplate,
    NotificationLog,
    NotificationRule,
    WebhookEndpoint
)
from django.contrib import admin


admin.site.register(NotificationProvider)
admin.site.register(Integration)
admin.site.register(NotificationTemplate)
admin.site.register(NotificationLog)
admin.site.register(NotificationRule)
admin.site.register(WebhookEndpoint)
