from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from math_trainer.utils.student_access_check import student_access_check

import logging

logger = logging.getLogger(__name__)


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = "math_trainer/common/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["classroom_id"] = self.request.GET.get("classroom_id")
        raw_student_id = self.request.GET.get("student_id")
        user = self.request.user
        student = student_access_check(user, raw_student_id)
        student_id = student.id
        context["student_id"] = student_id
        return context
