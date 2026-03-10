from django.urls import path

from audio_support.views import speak_word, speak_passage, speak_dialogue
# 削除周り
from audio_support.views import delete_temp_audio_post_batch, clean_old_temp_audio
# URL経由での再生機能実装

app_name = 'audio_support'

urlpatterns = [
    path('speak/word/', speak_word, name='speak_word'),
    path('speak/passage/', speak_passage, name='speak_passage'),
    path('speak/dialogue', speak_dialogue, name='speak_dialogue'),
    # クライアントサイドからのページ遷移時の一時音声ファイル削除
    path('delete_temp_audio_post_batch/', delete_temp_audio_post_batch, name='delete_temp_audio_post_batch'),
    # Google Cloud Schedulerからの定期タスク実行
    path("clean_old_temp_audio/", clean_old_temp_audio, name="clean_old_temp_audio"),
]