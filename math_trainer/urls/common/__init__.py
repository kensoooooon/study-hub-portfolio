from django.urls import include, path

app_name = "common"


urlpatterns = [
    path('', include('math_trainer.urls.common.scoring_urls')),
    # path('', include('math_trainer.urls.common.api_urls')), # 将来的な追加はこのような形で対応。順番に探索していく
]
