# line_channels/urls/__init__.py
from django.urls import include, path

app_name = "line_channels"

urlpatterns = [
    path("", include("line_channels.urls.global_urls")),  # ルートURLからのincludeを対処する
]
