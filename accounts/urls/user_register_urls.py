"""
名前未登録ユーザーのライン送信に対して、名前の登録を行う処理を担当
LINE経由のメールアドレス登録も本ファイルで管理する
"""
from django.urls import path
from ..views.line_views import RegisterNameView
from ..views.line_email_registration_views import RegisterEmailView


app_name = 'user_register'


urlpatterns = [
    path('register_name/<str:line_user_id>/', RegisterNameView.as_view(), name='register_name'),
    path('register_email/', RegisterEmailView.as_view(), name='register_email'),
]
