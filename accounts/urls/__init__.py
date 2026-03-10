"""
処理ごとに分割したURLの結合
"""

from django.urls import include, path


urlpatterns = [
    path('auth/', include('accounts.urls.auth_urls')),           # URL: /accounts/auth/login/
    path('user_register/', include('accounts.urls.user_register_urls')),           # URL: /accounts/user_register/register_name/
    path('organization_admin/', include('accounts.urls.organization_admin_urls')),
    path('student/', include('accounts.urls.student_urls')),
]