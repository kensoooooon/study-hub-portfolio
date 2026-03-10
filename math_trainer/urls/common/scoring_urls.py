from django.urls import include, path
from math_trainer.views.common.scoring_views import ScoringView, GradeResultView


urlpatterns = [
    path('score/', ScoringView.as_view(), name="score"),
    path('result/', GradeResultView.as_view(), name='result')
]
