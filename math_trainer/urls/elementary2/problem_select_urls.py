from django.urls import path

from math_trainer.views import elementary2


urlpatterns = [
    path('problem_select/', elementary2.ProblemSelectView.as_view(), name='problem_select'),
]