from django.urls import reverse
from django.conf import settings

from accounts.models import Student
from accounts.selectors import visible_students_qs


def homepage_url(request):
    """
    ログインユーザーのロールに応じてトップページURLを提供する
    """
    # 未ログインの場合はログインページへのリンクを返す
    if not request.user.is_authenticated:
        return {'homepage_url': reverse('accounts_auth:login')}

    # ロールごとにトップページURLを決定
    if request.user.role == 'organization_administrator':
        return {'homepage_url': reverse('organization_admin:classroom_list')}
    elif request.user.role == 'classroom_administrator':
        # 教室管理者もクエリセットから担当教室の一覧ページを表示
        return {'homepage_url': reverse('organization_admin:classroom_list')}
    elif request.user.role == 'teacher':
        return {'homepage_url': reverse('organization_admin:teacher_dashboard')}
    elif request.user.role == 'student':
        return {'homepage_url': reverse('student:home')}
    else:
        # 役割が不明な場合、デフォルトでログインページに戻す
        return {'homepage_url': reverse('accounts_auth:login')}


def unassigned_students_count(request):
    """
    未割り当ての生徒の数をコンテキストに追加
    """
    user = request.user
    if user.is_authenticated and user.role == "organization_administrator":
        student_qs = visible_students_qs(user)
        unassigned_students_count = student_qs.filter(
            classrooms__isnull=True,
            line_user_id__isnull=False,
        ).count()
        return {"unassigned_student_count": unassigned_students_count}
    return {"unassigned_student_count": 0}  # 組織管理者以外には見せない


def debug_mode(request):
    """
    テンプレートでローカルと本番環境を検知するためのテンプレートタグ用
    """
    return {'is_debug': settings.DEBUG}
