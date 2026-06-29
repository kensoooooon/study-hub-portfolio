"""
2025/11/9
未解決: 関係のないユーザー、関係のない画面で「～を更新しました」が出力される不具合?
→message...を削除するのが一番てっとり早い

2025/11/16
教室への割当の際に、きちんと組織の所属をチェックするように変更
"""
import logging


from django.views.generic import ListView, DetailView, UpdateView, CreateView, DeleteView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.http import HttpResponseNotAllowed, Http404
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views import View
from django.shortcuts import get_object_or_404

from accounts.models import Classroom
from accounts.models import Student, Teacher, BaseUser
from accounts.forms import StudentEditForm, TeacherEditForm, TeacherCreateForm, AccountEditForm, StudentEditForTeachersForm
from vocab_trainer.models import StudentContextProgress
from accounts.forms import ClassroomCreateForm, ClassroomEditForm, AssignClassroomForm
from accounts.selectors import visible_students_qs, visible_inactive_students_qs
from vocab_trainer.services.student_availability import has_vocab_progress

# ログ取得
logger = logging.getLogger(__name__)


def _get_classroom_id(request):
    classroom_id = request.GET.get('classroom_id') or request.POST.get('classroom_id')
    return None if classroom_id == 'None' else classroom_id


class ClassroomCreateView(LoginRequiredMixin, CreateView):
    model = Classroom
    form_class = ClassroomCreateForm
    template_name = 'accounts/organization_admin/classroom/create.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'organization_administrator':
            raise PermissionDenied("教室の作成権限がありません。")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        admin = self.request.user.get_role_object()
        organization = admin.organizations.first()
        if not organization:
            raise PermissionDenied("組織が見つかりません。")

        classroom = form.save(commit=False)
        classroom.organization = organization
        classroom.save()

        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('organization_admin:classroom_list')


class ClassroomEditView(LoginRequiredMixin, UpdateView):
    model = Classroom
    form_class = ClassroomEditForm
    template_name = 'accounts/organization_admin/classroom/edit.html'

    def dispatch(self, request, *args, **kwargs):
        classroom = self.get_object()
        role_object = request.user.get_role_object()

        if not role_object or not role_object.can_manage_classroom(classroom):
            raise PermissionDenied("この教室を編集する権限がありません。")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_user'] = self.request.user  # フォームに現在のユーザー情報を渡す
        return kwargs

    def get_success_url(self):
        return reverse_lazy('organization_admin:classroom_detail', kwargs={'pk': self.object.pk})


class ClassroomDeleteView(LoginRequiredMixin, DeleteView):
    model = Classroom
    template_name = 'accounts/organization_admin/classroom/delete.html'

    def dispatch(self, request, *args, **kwargs):
        classroom = self.get_object()
        role_object = request.user.get_role_object()

        if not role_object or not role_object.can_manage_classroom(classroom):
            raise PermissionDenied("この教室を削除する権限がありません。")
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('organization_admin:classroom_list')


class ClassroomListView(LoginRequiredMixin, ListView):
    model = Classroom
    template_name = 'accounts/organization_admin/classroom/list.html'
    context_object_name = 'classrooms'

    def get_queryset(self):
        """
        管理可能な教室を全て渡す
        """
        role_object = self.request.user.get_role_object()

        if role_object and hasattr(role_object, 'get_accessible_classrooms'):
            return role_object.get_accessible_classrooms()

        raise PermissionDenied("アクセス権限がありません。")

    def get_context_data(self, **kwargs):
        """コンテキスト経由で役職の日本語名と未割り当て生徒数を渡す"""
        context = super().get_context_data(**kwargs)
        context['user_role_display'] = self.request.user.get_role_display()
        return context


class ClassroomDetailView(LoginRequiredMixin, DetailView):
    model = Classroom
    template_name = 'accounts/organization_admin/classroom/detail.html'
    context_object_name = 'classroom'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        role_object = self.request.user.get_role_object()

        if not role_object or not hasattr(role_object, 'can_manage_classroom') or not role_object.can_manage_classroom(obj):
            raise PermissionDenied("この教室にアクセスする権限がありません。")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 学年ごとに生徒をグループ化して表示
        students_qs = visible_students_qs(self.request.user).filter(
            classrooms=self.object).order_by('grade').distinct()
        grouped_students = {}
        for student in students_qs:
            grouped_students.setdefault(student.get_grade_display(), []).append(student)
        context['grouped_students'] = grouped_students
        return context


class UnassignedStudentListView(LoginRequiredMixin, ListView):
    """
    教室に割り当てられていない生徒の一覧を表示する
    """
    template_name = "accounts/organization_admin/student/unassigned_students.html"
    context_object_name = "students"

    def get_queryset(self):
        user = self.request.user

        if user.role != "organization_administrator":  # visibleは他ロールにも使えるため、ロールの防御は別途こちらで
            logger.warning(
                "未割り当て生徒一覧への不正アクセスを検知しました。",
                extra={
                    "user_id": user.id,
                    "role": getattr(user, "role", None),
                    "view": "UnassignedStudentListView",
                },
            )
            raise PermissionDenied("アクセス権限がありません。")

        return visible_students_qs(user).filter(
            classrooms__isnull=True,
            line_user_id__isnull=False,
        )


class ClassroomAssignmentView(LoginRequiredMixin, FormView):
    """
    教室に割り当てられていない生徒を指定した教室に割り当てる
    """
    template_name = "accounts/organization_admin/student/assign_classroom.html"
    form_class = AssignClassroomForm
    success_url = reverse_lazy("organization_admin:unassigned_students")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role != "organization_administrator":
            logger.warning(
                "ClassroomAssignmentView への権限外アクセスを検知しました。",
                extra={
                    "user_id": request.user.id,
                    "role": getattr(request.user, "role", None),
                    "view": "ClassroomAssignmentView",
                },
            )
            raise PermissionDenied("アクセス権限がありません。")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user  # 🔑 フォームに管理者情報を渡す
        return kwargs

    def form_valid(self, form):
        student = form.save()
        messages.success(self.request, f"{student.username} さんを教室に割り当てました！")
        return super().form_valid(form)


class StudentDetailView(LoginRequiredMixin, DetailView):
    model = Student
    template_name = 'accounts/organization_admin/student/detail.html'
    context_object_name = 'student'

    def get_queryset(self):
        """
        詳細を取得しようとするオブジェクトのベースとなるビューを決定する
        """
        user = self.request.user
        if user.role == "student":
            raise PermissionDenied("このページにアクセスする権限がありません。")
        return visible_students_qs(user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classroom_id = _get_classroom_id(self.request)
        context['classroom_id'] = classroom_id
        context['reminders'] = self.object.study_reminders.ordered_by_day_and_time()
        context['has_vocab_history'] = has_vocab_progress(self.object)
        return context


class StudentEditView(LoginRequiredMixin, UpdateView):
    model = Student
    form_class = StudentEditForm
    template_name = 'accounts/organization_admin/student/edit.html'

    def get_success_url(self):
        classroom_id = _get_classroom_id(self.request) or ''
        return reverse_lazy('organization_admin:student_detail', kwargs={'pk': self.object.pk}) + f'?classroom_id={classroom_id}'

    def get_queryset(self):
        user = self.request.user
        if user.role in ["student", "teacher"]:
            raise PermissionDenied("このページにアクセスする権限がありません。")
        return visible_students_qs(user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classroom_id = _get_classroom_id(self.request)
        context['classroom_id'] = classroom_id
        student_id = self.object.id
        context['student_id'] = student_id
        return context

    def form_valid(self, form):
        response = super().form_valid(form)

        # パスワードリセット処理
        if form.cleaned_data.get("reset_password"):
            self.object.set_default_password()

        # ★ 教室と講師の整合性を補完する
        student = self.object
        student_classrooms = list(student.classrooms.all())
        student_teachers = list(student.teachers.all())

        for teacher in student_teachers:
            if teacher.organization_id and teacher.organization_id != student.organization_id:
                logger.error(
                    "教師と生徒の所属組織に不整合が生じています。",
                    extra={
                        "student_id": student.id,
                        "student_org_id": student.organization_id,
                        "teacher_id": teacher.id,
                        "teacher_org_id": teacher.organization_id,
                        "view": "StudentEditView",
                    },
                )
                continue

            for classroom in student_classrooms:
                if classroom.organization_id != student.organization_id:
                    logger.error(
                        "教室と生徒の所属組織に不整合が生じています。",
                        extra={
                            "student_id": student.id,
                            "student_org_id": student.organization_id,
                            "classroom_id": classroom.id,
                            "classroom_org_id": classroom.organization_id,
                            "view": "StudentEditView",
                        },
                    )
                    continue

                # 担当している生徒の所属教室が、講師側の所属教室に存在していない
                if not teacher.classrooms.filter(id=classroom.id).exists():
                    logger.info(
                        "teacher の所属教室に classroom を追加します。",
                        extra={
                            "student_id": student.id,
                            "teacher_id": teacher.id,
                            "classroom_id": classroom.id,
                            "view": "StudentEditView",
                        },
                    )
                    teacher.classrooms.add(classroom)

        messages.success(self.request, f"{self.object.username} の情報を更新しました")
        return response

    def get_form_kwargs(self):
        """
        ログインユーザーと編集中の生徒情報をフォームに渡して、
        teachers の queryset を絞り込めるようにする
        →formクラスで利用できるように、キーワード引数を設定する
        """
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        kwargs["student"] = self.object  # UpdateView では self.object に Student が入る
        return kwargs


class StudentDeleteView(LoginRequiredMixin, DeleteView):
    model = Student

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(['POST'])

    def get_queryset(self):
        user = self.request.user
        if user.role not in ["organization_administrator", "classroom_administrator"]:
            raise PermissionDenied("このページにアクセスする権限がありません。")
        return visible_students_qs(user)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user
        role_object = user.get_role_object()

        if user.role in ['organization_administrator', 'classroom_administrator']:
            if not role_object or not role_object.can_manage_student(obj):
                raise PermissionDenied("この生徒を削除する権限がありません。")
        else:
            raise PermissionDenied("このページにアクセスする権限がありません。")
        return obj

    def post(self, request, *args, **kwargs):  # post→form_valid→get_success_urlの後ろをカット
        self.object = self.get_object()
        classroom_id = _get_classroom_id(request)

        self.object.is_active = False
        self.object.save(update_fields=["is_active"])
        messages.success(request, "生徒を無効化しました。")

        if classroom_id:
            return redirect("organization_admin:classroom_detail", pk=classroom_id)
        return redirect("organization_admin:classroom_list")


class TeacherDashboardView(LoginRequiredMixin, ListView):
    """
    講師向けダッシュボード：担当生徒一覧を表示するビュー
    """
    model = Student
    template_name = 'accounts/organization_admin/teacher/dashboard.html'
    context_object_name = 'students'

    def get_queryset(self):
        # ログインユーザーが講師であることを確認
        user = self.request.user

        if user.role != 'teacher':
            raise PermissionDenied("講師のみアクセス可能です。")

        # 担当生徒を取得して返す
        students_qs = visible_students_qs(user).order_by('-grade')
        return students_qs


class TeacherEditView(LoginRequiredMixin, UpdateView):
    model = Teacher
    form_class = TeacherEditForm
    template_name = 'accounts/organization_admin/teacher/form.html'

    def dispatch(self, request, *args, **kwargs):
        teacher = self.get_object()
        role_object = request.user.get_role_object()

        if not role_object or not hasattr(teacher, 'can_be_accessed_by') or not teacher.can_be_accessed_by(request.user):
            logger.warning(f"Unauthorized access attempt by {request.user.username} to edit teacher {teacher.id}")
            raise PermissionDenied("この講師にアクセスする権限がありません")
        return super().dispatch(request, *args, **kwargs)


    def get_success_url(self):
        classroom_id = _get_classroom_id(self.request)
        if classroom_id:
            return reverse_lazy("organization_admin:classroom_detail", kwargs={"pk": classroom_id})
        return reverse_lazy("organization_admin:classroom_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classroom_id = _get_classroom_id(self.request)
        context["classroom_id"] = classroom_id
        context['next_url'] = self.request.GET.get('next', '')
        context['teacher'] = self.object
        context['classrooms'] = self.object.classrooms.all()
        context['action'] = '編集'  # ← ここを追加
        return context

    def form_valid(self, form):
        teacher = form.save(commit=False)
        classrooms = form.cleaned_data.get("classrooms")  # フォームの教室リストを取得

        if form.cleaned_data.get("reset_password"):
            teacher.set_default_password()

        teacher.save()
        teacher.classrooms.set(classrooms)  # ⭐ 教室の変更を反映

        messages.success(self.request, f"{teacher.username} の情報を更新しました")
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_user'] = self.request.user
        kwargs['classrooms_queryset'] = Classroom.objects.filter(id__in=[
            c.id for c in Classroom.objects.all() if c.can_be_accessed_by(self.request.user)
        ])
        return kwargs

        

class TeacherCreateView(LoginRequiredMixin, CreateView):
    """
    講師の新規作成ビュー
    """
    model = Teacher
    form_class = TeacherCreateForm
    template_name = 'accounts/organization_admin/teacher/form.html'
    success_url = reverse_lazy('organization_admin:classroom_detail')

    def dispatch(self, request, *args, **kwargs):
        # アクセス権限を確認
        if not request.user.role in ['organization_administrator', 'classroom_administrator']:
            raise PermissionDenied("アクセス権限がありません")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = '新規作成'
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_user'] = self.request.user
        kwargs['classrooms_queryset'] = Classroom.objects.filter(id__in=[
            c.id for c in Classroom.objects.all() if c.can_be_accessed_by(self.request.user)
        ])
        return kwargs


    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()):
            return next_url

        # 講師が複数の教室に所属している可能性があるため、最初の教室にリダイレクト
        classroom = self.object.classrooms.first()
        if classroom:
            return reverse_lazy('organization_admin:classroom_detail', kwargs={'pk': classroom.id})

        return reverse_lazy('organization_admin:classroom_list')  # デフォルトのリダイレクト先

    def form_valid(self, form):
        teacher = form.save()
        messages.success(self.request, f"講師 {teacher.username} を作成しました")
        return super().form_valid(form)


class TeacherDeleteView(LoginRequiredMixin, DeleteView):
    model = Teacher
    template_name = 'accounts/organization_admin/teacher/confirm_delete.html'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not obj.can_be_accessed_by(self.request.user):
            raise PermissionDenied("この講師へのアクセス権がありません")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["classroom_id"] = _get_classroom_id(self.request)
        return context

    def get_success_url(self):
        classroom_id = _get_classroom_id(self.request)
        messages.success(self.request, "講師を削除しました。")
        if classroom_id:
            return reverse_lazy("organization_admin:classroom_detail", kwargs={"pk": classroom_id})
        return reverse_lazy("organization_admin:classroom_list")


class AccountEditView(LoginRequiredMixin, UpdateView):
    model = BaseUser
    form_class = AccountEditForm
    template_name = 'accounts/organization_admin/common/account_edit.html'

    def get_success_url(self):
        """ パスワード変更後は強制ログアウトし、ログイン画面へ遷移 """
        return reverse('accounts_auth:login')  # すべてのユーザーをログイン画面へ

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        form.save()
        logout(self.request)
        messages.success(self.request, "パスワードを変更しました。再ログインしてください。")
        return redirect(reverse('accounts_auth:login'))


class StudentEditForTeachersView(LoginRequiredMixin, UpdateView):
    model = Student
    form_class = StudentEditForTeachersForm
    template_name = 'accounts/organization_admin/student/edit_for_teachers.html'

    def dispatch(self, request, *args, **kwargs):
        student = self.get_object()

        if request.user.role != 'teacher':
            raise PermissionDenied("講師以外はアクセスできません")

        teacher = request.user.get_role_object()
        if not teacher or student not in teacher.get_students():
            raise PermissionDenied("この生徒を編集する権限がありません")

        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        classroom_id = _get_classroom_id(self.request) or ''
        return reverse_lazy('organization_admin:student_detail', kwargs={'pk': self.object.pk}) + f'?classroom_id={classroom_id}'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if form.cleaned_data.get("reset_password"):
            self.object.set_default_password()
        messages.success(self.request, f"{self.object.username} の情報を更新しました")
        return response


class StudentReactivateView(LoginRequiredMixin, View):
    model = Student
    template_name = "accounts/organization_admin/classroom/reactivate_student.html"

    def dispatch(self, request, *args, **kwargs):
        """
        POST,GETの両方においてアクセスチェック

        Concerns:
            - ロールのチェックはget_role_objectで代替可能？可能なら省く
        """
        if not request.user.is_authenticated:  # 明示的にログイン画面に流す
            return self.handle_no_permission()
        user = request.user
        if not hasattr(user, "role"):  # ロールが設定されていない場合はアクセス不能
            raise PermissionDenied("この機能にアクセスする権限がありません。")
        if user.role not in ["organization_administrator", "classroom_administrator"]:  # 組織管理者か教室管理者以外はアクセス不能
            raise PermissionDenied("この機能にアクセスする権限がありません。")

        if not hasattr(user, "get_role_object"):  # ロールオブジェクトを持たないユーザーはアクセス不可
            raise PermissionDenied("この機能にアクセスする権限がありません。")
        role_object = user.get_role_object()
        if role_object is None:  # ロールに対応するオブジェクトを持たないユーザーはアクセス不可
            raise PermissionDenied("この機能にアクセスする権限がありません。")
        self.classroom_id = kwargs["classroom_id"]  # URLのパスから教室ID取得
        # classroom = Classroom.objects.get(id=self.classroom_id)
        classroom = get_object_or_404(Classroom, pk=self.classroom_id)
        if not hasattr(role_object, 'can_manage_classroom') or not role_object.can_manage_classroom(classroom):  # 判定メソッドが存在しない、あるいは判定が通らない場合はアクセス不可
            raise PermissionDenied("この教室にアクセスする権限がありません。")
        return super().dispatch(request, *args, **kwargs)  # 全てのチェックに通ったユーザーのみアクセス可能
    
    def get(self, request, *args, **kwargs):  # 非アクティブの生徒一覧をコンテキストで渡してチェックさせる系
        user = request.user  # dispatchを通っているので確認は不要
        students = visible_inactive_students_qs(user)  # 非アクティブな生徒を取得

        classroom = get_object_or_404(Classroom, pk=self.classroom_id)
        if not classroom.can_be_accessed_by(user):
            raise PermissionDenied("この教室にアクセスする権限がありません。")
        students = students.filter(classrooms=classroom).order_by('grade')  # 対象の教室に入っている生徒だけ見える
        if not students.exists():  # 処理の対象となる生徒がいるかの確認
            messages.warning(request, "対象となる生徒が存在しません。")
            return redirect("organization_admin:classroom_detail", pk=self.classroom_id)
        context = {}
        context["students"] = students
        context["classroom"] = classroom  #　パンくずリスト用
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):  # 受け取った生徒IDを復活処理
        user = request.user
        student_ids = request.POST.getlist("student_id")  # checkbox一括取得
        if not student_ids:
            messages.warning(request, "再アクティブ化したい生徒を選択して下さい。")
            return redirect("organization_admin:student_reactivate", classroom_id=self.classroom_id)
        classroom = get_object_or_404(Classroom, pk=self.classroom_id)
        if not classroom.can_be_accessed_by(user):
            raise PermissionDenied("この教室にアクセスする権限がありません。")
        base_qs = visible_inactive_students_qs(user).filter(classrooms=classroom)  # 念のため、対象を絞る
        for student_id in student_ids:
            student = base_qs.filter(id=student_id).first()  # エラーを吐かせない
            if student and (student.is_active == False):  # 生徒が取得できて、なおかつ非アクティブであれば処理
                student.is_active = True
                student.save()
                logger.info(
                    "生徒を再アクティブ化しました。",
                    extra = {
                        "user_id": user.id,
                        "target_student_id": student.id,
                        "classroom_id": self.classroom_id,
                        }
                    )
        messages.success(request, "生徒の再アクティブ化を完了しました")
        return redirect("organization_admin:classroom_detail", pk=self.classroom_id)
