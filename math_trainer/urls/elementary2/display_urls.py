from django.urls import path

from math_trainer.views import elementary2


urlpatterns = [
    path('', elementary2.Grade2DisplayDispatcherView.as_view(), name='dispatcher_display'),
    path('clock/', elementary2.ClockDisplayView.as_view(), name='clock_display'),
    path('clock/result/', elementary2.clock_result_view, name='clock_result'),
]