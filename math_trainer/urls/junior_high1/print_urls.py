from django.urls import path

from math_trainer.views import junior_high1

urlpatterns = [
    path('', junior_high1.JuniorHigh1PrintDispatcherView.as_view(), name='dispatcher_print'),
    path('specific_linear_equation/', junior_high1.SpecificLinearEquationPrintView.as_view(), name='specific_linear_equation_print'),
]
