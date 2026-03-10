from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from accounts.models import Student
from vocab_trainer.models import StudentContextProgress

from chem_trainer.models import StudentSubstanceProgress, StudentCompoundProgress, StudentEquationProgress


@login_required
def student_home(request):
    """ 生徒のホームページ """
    # ログインユーザーが Student であることを確認
    try:
        student = Student.objects.get(pk=request.user.pk)
    except Student.DoesNotExist:
        return redirect('accounts_auth:login')

    context = {
        'student': student
    }
    return render(request, 'accounts/student/home.html', context)


@login_required
def study_english_history(request):
    """ 優先度の高い順に 10 件の復習カードを表示 """
    student = Student.objects.get(pk=request.user.pk)

    # ✅ 復習優先度の高い順に 10 個を取得
    word_progresses = StudentContextProgress.objects.filter(student=student).order_by('-review_priority')[:10]
    context = {
        'student': student,
        'word_progresses': word_progresses,
    }
    return render(request, 'accounts/student/english_history.html', context)


@login_required
def study_english_history(request):
    """ 優先度の高い順に 10 件の復習カードを表示 """
    student = Student.objects.get(pk=request.user.pk)

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
    student = Student.objects.get(pk=request.user.pk)

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
