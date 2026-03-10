from django.urls import path
from .views import LineWebhookView

urlpatterns = [
    path('webhook/', LineWebhookView.as_view(), name='line_webhook'),
]
