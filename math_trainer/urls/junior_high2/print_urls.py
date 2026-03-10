from django.urls import path

from math_trainer.views import junior_high2

urlpatterns = [
    path('', junior_high2.JuniorHigh2PrintDispatcherView.as_view(), name='dispatcher_print'),
    path('simultaneous_equations/', junior_high2.SimultaneousEquationsPrintView.as_view(), name='simultaneous_equations_print'),
]
