# text_scheduler/views/materials.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.http import Http404
from django.views.generic import CreateView, UpdateView, DeleteView, ListView

from text_scheduler.models import LearningMaterial, StudentUnitProgress
from text_scheduler.forms import LearningMaterialForm

# daily plan
from text_scheduler.services.daily_plan import generate_or_get_today_plan, build_dto
from django.utils import timezone

# daily plan diagnosis
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from text_scheduler.services.feasibility import diagnose_plan
from datetime import date
from django.contrib import messages



from text_scheduler.access_policies import visible_materials_qs
from text_scheduler.access_policies import get_accessible_material_or_404, get_accessible_student_or_404


class MaterialAccessMixin(LoginRequiredMixin):
    """LearningMaterial用の共通アクセス制御。"""
    def get_queryset(self):
        # ID推測で他人のオブジェクトを触れないように、最初から絞る
        return visible_materials_qs(self.request.user)


class LearningMaterialListView(MaterialAccessMixin, ListView):
    model = LearningMaterial
    template_name = 'text_scheduler/material_list.html'
    context_object_name = 'materials'
    ordering = ['-start_date', '-id']
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        self.student = get_accessible_student_or_404(request)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()  # accessmixinを信頼
        student = self.student
        student_id = student.id
        if student_id:
            qs = qs.filter(target_student_id=student_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.student
        student_id = student.id
        classroom_id = self.request.GET.get("classroom_id") or self.request.POST.get("classroom_id")
        context["student_id"] = student_id
        context["classroom_id"] = classroom_id

        # 本日のプランと進捗を集計
        today = timezone.localdate()
        material_plans = {}
        material_progress = {}

        for m in context.get("materials", []):
            # 今日のプラン DTO
            plan = generate_or_get_today_plan(m, today)  # 既存実装に準拠
            material_plans[m.id] = build_dto(plan)

            required = max(0, int(m.required_reviews or 0))

            # 完了率集計（“完了”＝ total_reviews >= required_reviews）
            start = m.start_number or 0
            end = m.end_number or -1
            total_units = max(0, end - start + 1)
            completed_units = (
                StudentUnitProgress.objects
                .filter(material=m, total_reviews__gte=required, student=m.target_student,)
                .values("number").distinct().count()
            )
            started_units = (
                StudentUnitProgress.objects
                .filter(material=m, repetition_count__gt=0, student=m.target_student)
                .values("number").distinct().count()
            )
            # 完了率（従来）: completed / total
            rate = int(round(100 * completed_units / total_units)) if total_units else 0

            # ▼ 新: 進捗率（daily に増える数字）
            per_unit_cap = 1 + required
            denom_events = total_units * per_unit_cap

            # repetition_count の合計（番号ごとに cap を適用）
            # Progress は 1 番号 = 1 行（unique_together）なので values_list で良い
            rep_counts = (
                StudentUnitProgress.objects
                .filter(material=m, student=m.target_student,)
                .values_list("repetition_count", flat=True)
            )

            num_events_capped = sum(min(rc or 0, per_unit_cap) for rc in rep_counts)
            progress_rate = int(round(100 * num_events_capped / denom_events)) if denom_events else 0

            material_progress[m.id] = {
                "total": total_units,
                "completed": completed_units,
                "started": started_units,
                "rate": rate,                     # 従来の「完了率」
                "progress_rate": progress_rate,   # 新しい「進捗」
                "progress_num": num_events_capped,
                "progress_den": denom_events,
            }

        context["material_plans"] = material_plans
        context["material_progress"] = material_progress
        return context

class LearningMaterialCreateView(MaterialAccessMixin, CreateView):
    model = LearningMaterial
    form_class = LearningMaterialForm
    template_name = "text_scheduler/material_form.html"

    def dispatch(self, request, *args, **kwargs):
        self._target_student = get_accessible_student_or_404(request)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        ini = super().get_initial()
        # UX向上：デフォルト値をここで統一管理（未来でロジックを変えてもOK）
        ini.setdefault("unit_label", "番")
        ini.setdefault("required_reviews", 3)
        ini.setdefault("estimated_minutes_per_unit", 5)
        ini.setdefault("buffer_weekdays", [])
        return ini

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.target_student = self._target_student
        resp = super().form_valid(form)
        # forms.clean() で保持した診断結果があれば参照
        diag = getattr(form, "_diagnosis", None)
        if diag and diag.get("status") == "tight":
            fd = diag.get("first_deadline") or "（算出不可）"
            dd = diag.get("delay_days")
            messages.warning(
                self.request,
                f"この計画では最終復習が目標日に間に合わない可能性があります。"
                f" 初回学習の締切: {fd} / 遅延見込み: 約{dd}日"
            )
        return resp
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["student_id"] = str(self._target_student.id)
        ctx["classroom_id"] = self.request.GET.get("classroom_id") or self.request.POST.get("classroom_id")
        return ctx

    def _query_suffix(self):
        q = []
        # まず GET/POST を見る
        sid = self.request.GET.get("student_id") or self.request.POST.get("student_id")
        cid = self.request.GET.get("classroom_id") or self.request.POST.get("classroom_id")

        # それでも無ければ dispatch で確定済みのターゲットから補完
        if not sid and hasattr(self, "_target_student") and self._target_student:
            sid = str(self._target_student.id)

        if sid:
            q.append(f"student_id={sid}")
        if cid:
            q.append(f"classroom_id={cid}")
        return f"?{'&'.join(q)}" if q else ""

    def get_success_url(self):
        url = reverse("text_scheduler:material_list")
        return url + self._query_suffix()


class LearningMaterialUpdateView(MaterialAccessMixin, UpdateView):
    model = LearningMaterial
    form_class = LearningMaterialForm
    template_name = "text_scheduler/material_form.html"

    def get_object(self, queryset=None):
        return get_accessible_material_or_404(self.request)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 1) まずリクエストから拾う
        sid = self.request.GET.get("student_id") or self.request.POST.get("student_id")
        cid = self.request.GET.get("classroom_id") or self.request.POST.get("classroom_id")
        # 2) 無ければオブジェクトから補完（Update では常に obj がある）
        if not sid and getattr(self, "object", None):
            sid = str(self.object.target_student_id)
        context["student_id"] = sid
        context["classroom_id"] = cid
        # 3) 一部のパンくず分岐で生徒オブジェクトが必要になる場合に備え追加
        context["student"] = getattr(self.object, "target_student", None)
        return context

    def form_valid(self, form):
        resp = super().form_valid(form)
        diag = getattr(form, "_diagnosis", None)
        if diag and diag.get("status") == "tight":
            fd = diag.get("first_deadline") or "（算出不可）"
            dd = diag.get("delay_days")
            messages.warning(
                self.request,
                f"この計画では最終復習が目標日に間に合わない可能性があります。"
                f" 初回学習の締切: {fd} / 遅延見込み: 約{dd}日"
            )
        return resp
    
    def _query_suffix(self):
        q = []
        sid = self.request.GET.get("student_id") or self.request.POST.get("student_id")
        cid = self.request.GET.get("classroom_id") or self.request.POST.get("classroom_id")
        if sid: q.append(f"student_id={sid}")
        if cid: q.append(f"classroom_id={cid}")
        return f"?{'&'.join(q)}" if q else ""

    def get_success_url(self):
        url = reverse("text_scheduler:material_list")
        return url + self._query_suffix()


class LearningMaterialDeleteView(MaterialAccessMixin, DeleteView):
    model = LearningMaterial
    template_name = "text_scheduler/confirm_delete.html"
    success_url = reverse_lazy("text_scheduler:material_list")  # 一覧があれば

    def get_object(self, queryset=None):
        return get_accessible_material_or_404(self.request)

    def _query_suffix(self):
        q = []
        sid = self.request.GET.get("student_id") or self.request.POST.get("student_id")
        cid = self.request.GET.get("classroom_id") or self.request.POST.get("classroom_id")
        if sid: q.append(f"student_id={sid}")
        if cid: q.append(f"classroom_id={cid}")
        return f"?{'&'.join(q)}" if q else ""

    def get_success_url(self):
        url = reverse("text_scheduler:material_list")
        return url + self._query_suffix()


@require_GET
@login_required
def material_plan_preview(request):
    try:
        s_raw = request.GET.get("start")
        g_raw = request.GET.get("goal")
        u1_raw = request.GET.get("u1")
        u2_raw = request.GET.get("u2")
        if not all([s_raw, g_raw, u1_raw, u2_raw]):
            return JsonResponse({"error": "missing parameters"}, status=400)

        s = date.fromisoformat(s_raw)
        g = date.fromisoformat(g_raw)
        u1 = int(u1_raw)
        u2 = int(u2_raw)

        unit = int(request.GET.get("unit", 30))
        budget = int(request.GET.get("budget", 45))

        # 追加: 復習回数（未指定なら None → 従来の“復習無視”にフォールバック）
        reviews_raw = request.GET.get("reviews")
        required_reviews = int(reviews_raw) if reviews_raw not in (None, "") else None

        # 追加: 予備日（例: buffers=5&buffers=6）→ [5,6]
        buffers_raw_list = request.GET.getlist("buffers")
        buffer_weekdays = []
        for x in buffers_raw_list:
            try:
                v = int(x)
            except Exception:
                return JsonResponse({"error": "invalid parameters"}, status=400)
            if v < 0 or v > 6:
                return JsonResponse({"error": "invalid parameters"}, status=400)
            buffer_weekdays.append(v)

    except Exception:
        return JsonResponse({"error": "invalid parameters"}, status=400)

    data = diagnose_plan(
        s, g, u1, u2, unit, budget,
        required_reviews=required_reviews,         # ★ ここが追加
        buffer_weekdays=buffer_weekdays or None,   # ★ ここが追加（空ならNone）
        include_timeline= request.GET.get("detailed") == "1",
    )

    return JsonResponse(data, status=200)
