from django.views.generic import TemplateView
from django.shortcuts import redirect

from math_trainer.utils.student_access_check import student_access_check

class ProblemSelectView(TemplateView):
    template_name = "math_trainer/junior_high1/problem_select.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts_auth:login")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["classroom_id"] = self.request.GET.get("classroom_id")
        # context["student_id"] = self.request.GET.get("student_id")
        raw_student_id = self.request.GET.get("student_id")
        user = self.request.user
        student = student_access_check(user, raw_student_id)
        student_id = student.id
        context["student_id"] = student_id
        return context