from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test

from accounts.models import Student
from vocab_trainer.services import build_quiz_type_select_context
from vocab_trainer.access_policies import get_accessible_student_by_uuid_or_404

def is_student(user):
    """生徒のみアクセス可能"""
    return user.role == "student"


@login_required
@user_passes_test(is_student)
def quiz_type_select_for_student(request):
    """ 生徒用：クイズの種類選択画面 """
    classroom_id = None
    student = get_accessible_student_by_uuid_or_404(request.user, request.user.id)
    context = build_quiz_type_select_context(student, classroom_id)
    return render(request, 'vocab_trainer/quiz/for_student/quiz_type_select.html', context)
