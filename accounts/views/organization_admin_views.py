"""
2025/11/9
未解決: 関係のないユーザー、関係のない画面で「～を更新しました」が出力される不具合?
→message...を削除するのが一番てっとり早い

2025/11/16
教室への割当の際に、きちんと組織の所属をチェックするように変更
"""

from django.views.generic import ListView, DetailView, UpdateView, CreateView, DeleteView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy

from ..models import Classroom
from django.core.exceptions import PermissionDenied
from accounts.models import OrganizationAdministrator, ClassroomAdministrator, Student, Teacher, BaseUser
from accounts.forms import StudentEditForm, TeacherEditForm, TeacherCreateForm, AccountEditForm, StudentEditForTeachersForm

from vocab_trainer.models import StudentContextProgress

import logging

# 削除時のメッセージ用
from django.contrib import messages
# リダイレクト用
from django.urls import reverse
# nextの安全性確保
from django.utils.http import url_has_allowed_host_and_scheme

# 教室関連のform
from ..forms import ClassroomCreateForm, ClassroomEditForm, AssignClassroomForm

# ログアウト
from django.contrib.auth import logout
# redirect用
from django.shortcuts import redirect

# ログ取得
logger = logging.getLogger(__name__)

# 教材アプリのプロテクトへの対応
from django.db.models.deletion import ProtectedError


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
        students = self.object.students.order_by('grade')
        grouped_students = {}
        for student in students:
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
        if user.role != 'organization_administrator':
            raise PermissionDenied("アクセス権限がありません。")

        org_admin: OrganizationAdministrator = user.get_role_object()
        if not org_admin:
            raise PermissionDenied("組織管理者情報が取得できません。")

        # 🔐 管理している組織に属する生徒のみ
        return Student.objects.filter(
            organization__in=org_admin.organizations.all(),
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

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        role_object = self.request.user.get_role_object()

        if not role_object:
            raise PermissionDenied("このページにアクセスする権限がありません。")

        if hasattr(role_object, 'can_manage_classroom'):
            # 組織管理者・教室管理者が生徒を管理できるかチェック
            if not any(classroom for classroom in role_object.get_accessible_classrooms() if obj in classroom.students.all()):
                raise PermissionDenied("この生徒にアクセスする権限がありません。")
        elif hasattr(role_object, 'students'):
            # 講師が担当生徒であるかチェック
            if obj not in role_object.students.all():
                raise PermissionDenied("この生徒にアクセスする権限がありません。")
        else:
            raise PermissionDenied("このページにアクセスする権限がありません。")

        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classroom_id = self.request.GET.get('classroom_id') or self.request.POST.get('classroom_id')
        context['classroom_id'] = classroom_id
        context['reminders'] = self.object.study_reminders.ordered_by_day_and_time()
        # 長文学習への可否
        has_vocab_history = StudentContextProgress.objects.filter(
            student=self.object,
            total_count__gt=0
        ).exists()
        context['has_vocab_history'] = has_vocab_history
        return context


class StudentEditView(LoginRequiredMixin, UpdateView):
    model = Student
    form_class = StudentEditForm
    template_name = 'accounts/organization_admin/student/edit.html'

    def get_success_url(self):
        classroom_id = self.request.POST.get('classroom_id') or ''
        return reverse_lazy('organization_admin:student_detail', kwargs={'pk': self.object.pk}) + f'?classroom_id={classroom_id}'

    def get_object(self, queryset=None):
        # 生徒オブジェクトを取得し、アクセス制限を実施
        obj = super().get_object(queryset)
        user = self.request.user

        if user.role == 'organization_administrator':
            organization_admin = OrganizationAdministrator.objects.get(pk=user.pk)
            if not organization_admin.organizations.filter(classrooms__students=obj).exists():
                raise PermissionDenied("この生徒を編集する権限がありません。")
        elif user.role == 'classroom_administrator':
            classroom_admin = ClassroomAdministrator.objects.get(pk=user.pk)
            if not classroom_admin.classrooms.filter(students=obj).exists():
                raise PermissionDenied("この生徒を編集する権限がありません。")
        else:
            raise PermissionDenied("このページにアクセスする権限がありません。")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classroom_id = self.request.GET.get('classroom_id') or self.request.POST.get('classroom_id')
        context['classroom_id'] = classroom_id
        student_id = self.object.id
        context['student_id'] = student_id
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if form.cleaned_data.get("reset_password"):
            self.object.set_default_password()
        messages.success(self.request, f"{self.object.username} の情報を更新しました")
        return response

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
    template_name = 'accounts/organization_admin/student/confirm_delete.html'

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

    def delete(self, request, *args, **kwargs):
        """生徒削除時に ProtectedError を握ってユーザ向けメッセージを出す"""
        self.object = self.get_object()
        classroom_id = request.POST.get("classroom_id") or request.GET.get("classroom_id")

        try:
            self.object.delete()
            messages.success(request, "生徒を削除しました。")
        except ProtectedError:
            # created_by=PROTECT に引っかかった場合はこちら
            messages.error(
                request,
                "この生徒が作成した教材が残っているため削除できません。"
                "先に教材を削除するか、作成者を他のユーザーに変更してください。"
            )

        # どちらの場合でも、元の画面に戻す
        if classroom_id:
            return redirect("organization_admin:classroom_detail", pk=classroom_id)
        return redirect("organization_admin:classroom_list")

    def get_success_url(self):
        classroom_id = self.request.POST.get("classroom_id") or self.request.GET.get("classroom_id")
        messages.success(self.request, "生徒を削除しました。")
        if classroom_id:
            return reverse_lazy("organization_admin:classroom_detail", kwargs={"pk": classroom_id})
        return reverse_lazy("organization_admin:classroom_list")

    

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
        teacher = Teacher.objects.get(pk=user.pk)
        return teacher.get_students()


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
        classroom_id = self.request.GET.get("classroom_id") or self.request.POST.get("classroom_id")
        if classroom_id:
            return reverse_lazy("organization_admin:classroom_detail", kwargs={"pk": classroom_id})
        return reverse_lazy("organization_admin:classroom_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classroom_id = self.request.GET.get("classroom_id") or self.request.POST.get("classroom_id")
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
        context["classroom_id"] = self.request.POST.get("classroom_id") or self.request.GET.get("classroom_id")
        return context

    def get_success_url(self):
        classroom_id = self.request.POST.get("classroom_id") or self.request.GET.get("classroom_id")
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
        user = form.save()
        user.is_first_login = False  # ⭐ 初回ログインフラグを解除
        user.save()  # 必須（.save(commit=False) されている可能性あり
        logout(self.request)  # ⭐ パスワード変更後にログアウト
        messages.success(self.request, "パスワードを変更しました。再ログインしてください。")
        return redirect(reverse('accounts_auth:login'))  # ログイン画面にリダイレクト


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
        classroom_id = self.request.GET.get('classroom_id')
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