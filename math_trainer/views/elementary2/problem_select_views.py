from django.views.generic import TemplateView

from django.contrib.auth.mixins import LoginRequiredMixin

from math_trainer.utils.student_access_check import student_access_check

class ProblemSelectView(LoginRequiredMixin, TemplateView):
    template_name = "math_trainer/elementary2/problem_select.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 任意：パンくずリストで使用する classroom_id などを追加
        context["classroom_id"] = self.request.GET.get("classroom_id")
        # context["student_id"] = self.request.GET.get("student_id")
        raw_student_id = self.request.GET.get("student_id")
        user = self.request.user
        student = student_access_check(user, raw_student_id)
        student_id = student.id
        context["student_id"] = student_id
        return context
