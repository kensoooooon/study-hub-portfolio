from django.urls import path

from math_trainer.views import elementary2


urlpatterns = [
    path('', elementary2.Grade2PrintDispatcherView.as_view(), name='dispatcher_print'),
    path('clock/', elementary2.ClockPrintView.as_view(), name='clock_print'),
]