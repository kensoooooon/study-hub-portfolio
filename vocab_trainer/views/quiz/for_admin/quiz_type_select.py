from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test


from vocab_trainer.services import build_quiz_type_select_context
from vocab_trainer.access_policies import get_accessible_student_by_uuid_or_404


def is_admin_or_teacher(user):
    """ 管理者・講師のみアクセス可能 """
    return user.role in ['teacher', 'classroom_administrator', 'organization_administrator']


@login_required
@user_passes_test(is_admin_or_teacher)
def quiz_type_select_with_admin(request):
    classroom_id = request.POST.get("classroom_id") or request.GET.get("classroom_id") or ""
    target_student_id = request.POST.get("target_student_id") or request.GET.get("target_student_id") or ""

    if target_student_id:
        student = get_accessible_student_by_uuid_or_404(request.user, target_student_id)
        context = build_quiz_type_select_context(student, classroom_id)
        return render(request, "vocab_trainer/quiz/for_admin/quiz_type_select.html", context)

    # target_student_id が無いときだけ「役割別ホームへ」
    if request.user.role in ["organization_administrator", "classroom_administrator"]:
        return redirect("organization_admin:classroom_list")
    if request.user.role == "teacher":
        return redirect("organization_admin:teacher_dashboard")
    return redirect("accounts_auth:login")
