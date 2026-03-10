from django.urls import path

from math_trainer.views import junior_high1

urlpatterns = [
    path('', junior_high1.JuniorHigh1DisplayDispatcherView.as_view(), name='dispatcher_display'),
    path('specific_linear_equation/', junior_high1.SpecificLinearEquationDisplayView.as_view(), name='specific_linear_equation_display'),
    path('specific_linear_equation/result/', junior_high1.specific_linear_equation_result_view, name='specific_linear_equation_result'),
]