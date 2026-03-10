from django.urls import path

from math_trainer.views import junior_high1


urlpatterns = [
    path('problem_select/', junior_high1.ProblemSelectView.as_view(), name='problem_select'),
]