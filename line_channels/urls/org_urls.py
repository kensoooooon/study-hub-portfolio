from django.urls import path
from line_channels.views import OrganizationLineChannelCreateView


app_name = "org_line_channels"
urlpatterns = [
    # accountsアプリケーションの組織詳細画面からの処理の委託 URL: organizations/<int:org_pk>/line-channels/new/
    path("new/", OrganizationLineChannelCreateView.as_view(), name="org_new"),
]
