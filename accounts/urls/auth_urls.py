"""
ログイン、ログアウトなどの認証を担当
"""
from django.urls import path
from accounts.views import CustomLoginView, CustomLogoutView


app_name = 'accounts_auth'


urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
]
