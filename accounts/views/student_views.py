from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from vocab_trainer.models import StudentContextProgress
from vocab_trainer.services.student_availability import has_vocab_progress
from chem_trainer.models import StudentSubstanceProgress, StudentCompoundProgress, StudentEquationProgress
from accounts.selectors import get_visible_self_student


@login_required
def student_home(request):
    """ 生徒のホームページ """
    student = get_visible_self_student(request.user)
    if student is None:
        return redirect('accounts_auth:login')

    context = {
        'student': student,
        'has_vocab_progress': has_vocab_progress(student),  # 進捗が1件以上存在するか
    }
    return render(request, 'accounts/student/home.html', context)


@login_required
def study_english_history(request):
    """ 優先度の高い順に 10 件の復習カードを表示 """
    student = get_visible_self_student(request.user)
    if student is None:
        return redirect('accounts_auth:login')


    progresses = StudentContextProgress.objects.filter(student=student)
    if student.textbook:
        progresses = progresses.filter(context__chapter__textbook=student.textbook)

    word_progresses = progresses.order_by('-review_priority')[:10]

    context = {
        'student': student,
        'word_progresses': word_progresses,
    }
    return render(request, 'accounts/student/english_history.html', context)



@login_required
def study_chemical_history(request):
    """ 優先度の高い順に 10 件の復習カードを表示 """
    student = get_visible_self_student(request.user)
    if student is None:
        return redirect('accounts_auth:login')

    # ✅ 単体, 化合物, 化学式を復習優先度の高い順に 10 件ずつ取得
    substance_progresses = list(StudentSubstanceProgress.objects.filter(student=student).order_by('-review_priority')[:10])
    compound_progresses = list(StudentCompoundProgress.objects.filter(student=student).order_by('-review_priority')[:10])
    chemical_equation_progresses = list(StudentEquationProgress.objects.filter(student=student).order_by('-review_priority')[:10])

    # ✅ 取得したものをリストに統合し、優先度で並び替え
    all_progresses = substance_progresses + compound_progresses + chemical_equation_progresses
    sorted_progresses = sorted(all_progresses, key=lambda p: p.review_priority, reverse=True)

    # ✅ 上位10件を選択
    chemical_progresses = sorted_progresses[:10]

    context = {
        'student': student,
        'chemical_progresses': chemical_progresses,
    }
    return render(request, 'accounts/student/chemical_history.html', context)
