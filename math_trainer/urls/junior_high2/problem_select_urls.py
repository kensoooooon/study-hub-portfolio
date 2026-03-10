from django.urls import path

from math_trainer.views import junior_high2


urlpatterns = [
    path('problem_select/', junior_high2.ProblemSelectView.as_view(), name='problem_select'),
]