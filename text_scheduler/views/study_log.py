# text_scheduler/views/studylog.py
from django.views.generic import FormView
from django.shortcuts import redirect, render
from django.urls import reverse
from django.db import transaction

from text_scheduler.models import StudyLog
from text_scheduler.forms import StudyLogForm
from text_scheduler.services import apply_study_log

from urllib.parse import urlencode

from text_scheduler.forms import StudyLogFormSet
from django.views import View
from django.contrib import messages

from text_scheduler.access_policies import get_accessible_student_or_404, get_accessible_material_or_404

from django.http import Http404


class StudyLogCreateView(FormView):
    template_name = "text_scheduler/studylog_form.html"
    form_class = StudyLogForm

    def dispatch(self, request, *args, **kwargs):
        self.student = get_accessible_student_or_404(request)
        self.material = get_accessible_material_or_404(request)
        if self.student.id != self.material.target_student.id:  # 対象生徒の教材か?
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        ini = super().get_initial()
        ini["kind"] = self.request.GET.get("kind") or "review"
        n = self.request.GET.get("number")
        if n and n.isdigit():
            ini["number"] = int(n)
        return ini

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["student"] = self.student
        ctx["material"] = self.material

        # パンくず用IDを文脈に乗せる
        classroom_id = self.request.GET.get("classroom_id") or self.request.POST.get("classroom_id")

        ctx["student_id"] = self.student.id
        ctx["classroom_id"] = classroom_id
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = StudyLog(student=self.student, material=self.material)
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        log: StudyLog = form.save(commit=False)
        log.student = self.student
        log.material = self.material
        log.full_clean()
        log.save()

        apply_study_log(log)

        # 一覧へ戻る（パンくず用クエリを引き継ぐ）
        url = reverse("text_scheduler:material_list")
        qs = {"student_id": str(self.student.id)}
        classroom_id = self.request.GET.get("classroom_id") or self.request.POST.get("classroom_id")
        if classroom_id:
            qs["classroom_id"] = str(classroom_id)

        return redirect(f"{url}?{urlencode(qs)}")

    def form_invalid(self, form):
        messages.error(self.request, "入力内容にエラーがあります。各項目のエラー表示をご確認ください。")
        return self.render_to_response(self.get_context_data(form=form))


class StudyLogBulkCreateView(View):
    template_name = "text_scheduler/studylog_formset.html"
    formset_prefix = "logs"

    def dispatch(self, request, *args, **kwargs):
        self.student = get_accessible_student_or_404(request)
        self.material = get_accessible_material_or_404(request)
        if self.student.id != self.material.target_student.id:  # 対象生徒の教材か?
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def _make_context(self, formset):
        # パンくず用ID引き継ぎ
        student_id = self.kwargs.get("student_id") or self.request.GET.get("student_id")
        classroom_id = self.request.GET.get("classroom_id") or self.request.POST.get("classroom_id")
        return {
            "formset": formset,
            "student": self.student,
            "material": self.material,
            "student_id": student_id,
            "classroom_id": classroom_id,
        }

    def get(self, request, *args, **kwargs):
        formset = StudyLogFormSet(
            prefix=self.formset_prefix,
            form_kwargs={"student": self.student, "material": self.material},  # ★追加
        )
        return render(request, self.template_name, self._make_context(formset))

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        formset = StudyLogFormSet(
            request.POST,
            prefix=self.formset_prefix,
            form_kwargs={"student": self.student, "material": self.material},  # ★追加
        )

        if not formset.is_valid():
            return render(request, self.template_name, self._make_context(formset))

        saved = 0
        for form in formset:
            if not form.cleaned_data:
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            log: StudyLog = form.save(commit=False)
            log.student = self.student
            log.material = self.material
            log.full_clean()
            log.save()
            apply_study_log(log)
            saved += 1

        messages.success(request, f"{saved}件の成果を登録しました。")

        # 一覧へ戻る（パンくず用クエリを引き継ぐ）
        url = reverse("text_scheduler:material_list")
        qs = {"student_id": str(self.student.id)}
        classroom_id = request.GET.get("classroom_id") or request.POST.get("classroom_id")
        if classroom_id:
            qs["classroom_id"] = str(classroom_id)
        return redirect(f"{url}?{urlencode(qs)}")
