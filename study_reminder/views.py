from django.http import JsonResponse
from django.utils.timezone import localtime
from datetime import timedelta
from django.db import models
from .models import StudyReminder

# 管理画面作成用
from django.views.generic import ListView, UpdateView, DeleteView, CreateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import StudyReminderCreateForm, StudyReminderEditForm

# 権限用
from django.shortcuts import render

# リマインダーのアコーディオン表示用
from accounts.models import Student

# データ取得順保持のため
from django.db.models import Prefetch
from django.db.models import Case, When
from collections import defaultdict
from django.urls import reverse
from django.core.exceptions import PermissionDenied

# 環境の読み込み用
from django.conf import settings

# csrf検証の無効化
from django.views.decorators.csrf import csrf_exempt
# nextの安全性確保
from django.utils.http import url_has_allowed_host_and_scheme
# delete時の削除メッセージ
from django.contrib import messages

from django.http import HttpResponseRedirect

# ログ
import logging

# OIDC認証
from auth.oidc_verify import require_oidc_token

from django.contrib.auth.decorators import login_required

from study_reminder.utils.student_access_check import student_access_check

from django.http import Http404


logger = logging.getLogger(__name__)


@csrf_exempt
@require_oidc_token(audience=settings.OIDC_AUDIENCE)
def process_reminders(request):
    """
    Google Cloud Schedulerのトリガーポイントでリマインダーを処理（30分単位）
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    # 本番環境でのアクセス制限
    if settings.ENV != 'local':
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if user_agent != 'Google-Cloud-Scheduler':
            logger.warning(f"Unauthorized access attempt with User-Agent: {user_agent}")
            return JsonResponse({"error": "Unauthorized access"}, status=403)

    # 現在の時刻を直前の15分スロットに丸める
    current_time = localtime()
    current_time = current_time.replace(
        minute=(current_time.minute // 15) * 15,
        second=0,
        microsecond=0
    )
    next_time = current_time + timedelta(minutes=15)

    # 現在の曜日
    current_day = current_time.strftime('%A').lower()

    # 現在の15分スロットに該当するリマインダーを取得
    reminders = StudyReminder.objects.filter(
        day_of_week=current_day,
        time_of_day__gte=current_time.time(),
        time_of_day__lt=next_time.time(),
        is_active=True
    ).filter(
        models.Q(last_notified__lt=current_time.date()) | models.Q(last_notified__isnull=True)
    )

    # リマインダーを処理
    processed_count = 0
    for reminder in reminders:
        logger.info(f"Processing reminder for student: {reminder.student.username}, LINE ID: {reminder.student.line_user_id}")
        reminder.send_notification()
        reminder.last_notified = current_time.date()
        reminder.save(update_fields=["last_notified"])
        processed_count += 1

    # 処理結果をログに記録
    logger.info(f"Processed {processed_count} reminders for time slot: {current_time.time()} - {next_time.time()}")

    return JsonResponse({"status": "success", "processed_reminders": processed_count})


# リマインダー管理画面用(常用はしない)
class ReminderListView(LoginRequiredMixin, ListView):
    model = StudyReminder
    template_name = 'study_reminder/reminder_list.html'
    context_object_name = 'reminders'

    def get_queryset(self):
        return StudyReminder.objects.filter_by_access(self.request.user)


class ReminderEditView(LoginRequiredMixin, UpdateView):
    """
    リマインダー編集画面用のビュー
    """
    model = StudyReminder
    form_class = StudyReminderEditForm
    template_name = 'study_reminder/reminder_form.html'

    def get_object(self, queryset=None):
        try:
            obj = super().get_object(queryset)
        except StudyReminder.DoesNotExist:
            raise PermissionDenied("このリマインダーは存在しません。")

        if not obj.can_be_accessed_by(self.request.user):
            raise PermissionDenied("このリマインダーへのアクセス権がありません。")
        return obj

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()):
            return next_url
        else:
            user = self.request.user
            if user.role == "organization_administrator":
                return reverse('organization_admin:classroom_list')
            elif user.role == "classroom_administrator":
                return reverse('organization_admin:classroom_list')
            elif user.role == "teacher":
                return reverse('organization_admin:teacher_dashboard')

    def get_initial(self):
        initial = super().get_initial()
        reminder = self.get_object()

        # すでに設定されている曜日、時間、メッセージを初期値として設定
        initial['day_of_week'] = reminder.day_of_week
        initial['time_of_day'] = reminder.time_of_day.strftime('%H:%M')
        initial['custom_message'] = reminder.custom_message or "ChatGPTの自動メッセージ"

        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['next'] = self.request.GET.get('next', '')
        context['student'] = self.object.student
        return context

class ReminderDeleteView(LoginRequiredMixin, DeleteView):
    model = StudyReminder
    template_name = 'study_reminder/reminder_confirm_delete.html'
    # success_url = reverse_lazy('student_list')

    def get_object(self, queryset=None):
        try:
            obj = super().get_object(queryset)
        except StudyReminder.DoesNotExist:
            raise PermissionDenied("このリマインダーは存在しません。")

        if not obj.can_be_accessed_by(self.request.user):
            raise PermissionDenied("このリマインダーへのアクセス権がありません。")
        return obj


    def post(self, request, *args, **kwargs):
        """
        削除処理を冪等にする:
        - アクセス可能なリマインダーだけを対象にdelete
        - 0件でも404を出さずにそのままリダイレクト
        """
        pk = self.kwargs.get("pk")

        # ユーザーがアクセス可能な範囲に限定して削除
        qs = StudyReminder.objects.filter_by_access(request.user).filter(pk=pk)
        deleted_count, _ = qs.delete()

        if deleted_count > 0:
            messages.success(request, "リマインダーを削除しました。")
        else:
            # すでに削除済み or そもそも権限外のリマインダー
            # → あえて「既に削除済み」として扱うことで情報漏えいを防ぐ
            messages.info(request, "このリマインダーは既に削除されています。")

        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()):
            return next_url
        else:
            user = self.request.user
            if user.role == "organization_administrator":
                return reverse('organization_admin:classroom_list')
            elif user.role == "classroom_administrator":
                return reverse('organization_admin:classroom_list')
            elif user.role == "teacher":
                return reverse('organization_admin:teacher_dashboard')


class ReminderCreateView(LoginRequiredMixin, CreateView):
    model = StudyReminder
    form_class = StudyReminderCreateForm
    template_name = 'study_reminder/reminder_create.html'

    def form_valid(self, form):
        user = self.request.user   
        raw_student_id = self.request.GET.get("student")

        try:
            student = student_access_check(user, raw_student_id)
        except PermissionDenied:
            # 403にする（ここを握りつぶさない）
            raise
        except Http404:
            form.add_error(None, "指定された生徒が存在しません。")
            return self.form_invalid(form)
        except Exception:
            logger.exception("生徒の取得中に想定外エラー (user.id=%s, raw_student_id=%s)", getattr(user, "id", None), raw_student_id)
            form.add_error(None, "エラーが発生しました。もう一度お試しください。")
            return self.form_invalid(form)

        form.instance.student = student
        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)

    def get_form_kwargs(self):
        """
        フォームにユーザー情報を渡す。
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()):
            return next_url

        # ユーザーのロールに応じたリダイレクト
        user = self.request.user
        if user.role == "organization_administrator":
            return reverse('organization_admin:classroom_list')
        elif user.role == "classroom_administrator":
            return reverse('organization_admin:classroom_list')
        elif user.role == "teacher":
            return reverse('organization_admin:teacher_dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student_id = self.request.GET.get('student')
        classroom_id = self.request.GET.get('classroom_id')
        if student_id:
            context['student_id'] = student_id
        if classroom_id:
            context['classroom_id'] = classroom_id
        return context


class StudentListView(LoginRequiredMixin, ListView):
    model = Student
    template_name = 'study_reminder/student_list.html'
    context_object_name = 'students'

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        role_obj = user.get_role_object() if role else None

        # 念のため role_obj が取れない場合は何も返さない
        if role_obj is None:
            return Student.objects.none()

        # 各生徒にぶら下げるリマインダーは、必ず filter_by_access 経由で取得
        reminder_qs = StudyReminder.objects.filter_by_access(user)

        # ◆ 組織管理者
        if role == 'organization_administrator':
            # OrganizationAdministrator.organizations (M2M)
            orgs = role_obj.organizations.all()
            if not orgs.exists():
                return Student.objects.none()

            return (
                Student.objects
                .filter(organization__in=orgs)
                .prefetch_related(
                    Prefetch('study_reminders', queryset=reminder_qs)
                )
                .distinct()
            )

        # ◆ 教室管理者
        elif role == 'classroom_administrator':
            # ClassroomAdministrator.classrooms / organization
            classrooms = role_obj.classrooms.all()
            qs = Student.objects.filter(classrooms__in=classrooms).distinct()

            if role_obj.organization:
                qs = qs.filter(organization=role_obj.organization)

            return qs.prefetch_related(
                Prefetch('study_reminders', queryset=reminder_qs)
            )

        # ◆ 講師
        elif role == 'teacher':
            # Student.teachers は Teacher モデル向けなので teachers=role_obj の方が素直
            qs = Student.objects.filter(teachers=role_obj).distinct()

            if getattr(role_obj, "organization", None):
                qs = qs.filter(organization=role_obj.organization)

            return qs.prefetch_related(
                Prefetch('study_reminders', queryset=reminder_qs)
            )

        # ◆ その他のロールには見せない
        return Student.objects.none()


@login_required
def get_reminders_by_student(request, student_id):
    user = request.user

    # 1) 生徒アクセスチェック（URL引数を渡すのが正解）
    try:
        student = student_access_check(user, str(student_id))
    except PermissionDenied:
        return JsonResponse({"error": "アクセス権がありません。"}, status=403)
    except Http404:
        # 「存在しない」か「見せない」を統一するなら 403 でOK
        logger.warning("student not found or not accessible (user.id=%s, student_id=%s)", getattr(user, "id", None), student_id)
        return JsonResponse({"error": "アクセス権がありません。"}, status=403)
    except Exception:
        logger.exception("student_access_check unexpected error (user.id=%s, student_id=%s)", getattr(user, "id", None), student_id)
        return JsonResponse({"error": "アクセス権がありません。"}, status=403)

    # 2) リマインダー取得
    try:
        day_order = Case(
            When(day_of_week="monday", then=1),
            When(day_of_week="tuesday", then=2),
            When(day_of_week="wednesday", then=3),
            When(day_of_week="thursday", then=4),
            When(day_of_week="friday", then=5),
            When(day_of_week="saturday", then=6),
            When(day_of_week="sunday", then=7),
        )

        reminders_qs = (
            StudyReminder.objects
            .filter_by_access(user)      # ここが最終防衛ラインで良い :contentReference[oaicite:0]{index=0}
            .filter(student_id=student.id)
            .order_by(day_order, "time_of_day")
        )

        grouped = defaultdict(list)
        for r in reminders_qs:
            grouped[r.get_day_of_week_display()].append({
                "id": r.id,
                "time_of_day": r.time_of_day.strftime("%H:%M"),
                "custom_message": r.custom_message or "メッセージなし(自動生成されたメッセージが送信されます)",
            })

        return JsonResponse({"reminders": grouped})
    except Exception:
        logger.exception("get_reminders_by_student failed (user.id=%s, student_id=%s)", getattr(user, "id", None), student.id)
        return JsonResponse({"error": "エラーが発生しました。"}, status=500)
