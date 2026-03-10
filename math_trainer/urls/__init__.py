from django.urls import include, path

app_name = "math_trainer"


urlpatterns = [
    path("", include("math_trainer.urls.index_urls")),
    path('common/', include('math_trainer.urls.common')),
    path('elementary2/', include('math_trainer.urls.elementary2')),
    path('junior_high1/', include('math_trainer.urls.junior_high1')),
    path('junior_high2/', include('math_trainer.urls.junior_high2')),
]
