from django.urls import path

from math_trainer.views import common

urlpatterns = [
    path("index", common.IndexView.as_view(), name="index"),
]
