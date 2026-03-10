from django.urls import path

from math_trainer.views import junior_high2

urlpatterns = [
    path('', junior_high2.JuniorHigh2DisplayDispatcherView.as_view(), name='dispatcher_display'),
    path('simultaneous_equations/', junior_high2.SimultaneousEquationsDisplayView.as_view(), name='simultaneous_equations_display'),
    path('simultaneous_equations/result/', junior_high2.simultaneous_equations_result_view, name='simultaneous_equations_result'),
]