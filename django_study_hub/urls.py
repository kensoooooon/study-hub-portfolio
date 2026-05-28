"""
URL configuration for django_study_hub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from audio_support.views import serve_temp_audio

handler403 = 'accounts.views.custom_permission_denied_view'


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),  # アカウント関連
    path('conversations/', include('conversations.urls')),  # 既存のconversationsアプリ(現状利用予定なし)
    path('line/', include('line_integration.urls')),  # LINE連携用アプリ
    path('study_reminder/', include('study_reminder.urls')),  # 学習時間リマインド用アプリ
    path('vocab_trainer/', include('vocab_trainer.urls')),  # 英単語クイズ用
    # path('chem_trainer/', include('chem_trainer.urls')),  # 化学クイズ用
    path('read_trainer/', include('read_trainer.urls')),  # 長文問題用
    # path('kobun_trainer/', include('kobun_trainer.urls')),  # 古文単語用
    path('audio_support/', include('audio_support.urls')),  # 音声サポート用
    path('listening_trainer/', include('listening_trainer.urls')),  # リスニング練習
    path('math_trainer/', include('math_trainer.urls')),  # 数学練習
    path('text_scheduler/', include('text_scheduler.urls')),  # テキストとスケジュール管理
    path('line_channels/', include('line_channels.urls')),  # チャンネル情報管理
    # URLのルーティング経由でファイルレスポンスを返却
    path("media/temp_audio/<str:filename>", serve_temp_audio, name="serve_temp_audio"),
    
]


# 音声再生用
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)