"""
名前未登録ユーザーのライン送信に対して、名前の登録を行う処理を担当
"""
from django.urls import path
from ..views.line_views import RegisterNameView


app_name = 'user_register'


urlpatterns = [
    path('register_name/<str:line_user_id>/', RegisterNameView.as_view(), name='register_name'),
]
