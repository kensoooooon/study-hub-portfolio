from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404

from vocab_trainer.services import (
    get_choices,
    build_quiz_type_select_context,
    pick_review_context_by_softmax
    )
from vocab_trainer.access_policies import get_accessible_student_by_uuid_or_404

import random
import logging


logger = logging.getLogger(__name__)


def is_admin_or_teacher(user):
    """ 管理者・講師のみアクセス可能 """
    return user.role in ['teacher', 'classroom_administrator', 'organization_administrator']

def error_handling_to_quiz_error(request, *, status=404):
    student_id = request.POST.get("target_student_id") or request.GET.get("target_student_id")
    classroom_id = request.POST.get("classroom_id") or request.GET.get("classroom_id")
    ctx = {"student_id": student_id, "classroom_id": classroom_id}
    return render(request, "vocab_trainer/quiz/for_admin/quiz_error.html", ctx, status=status)


def error_handling_to_textbook_not_found(request, *, status=404):
    student_id = request.POST.get("target_student_id") or request.GET.get("target_student_id")
    classroom_id = request.POST.get("classroom_id") or request.GET.get("classroom_id")
    ctx = {"student_id": student_id, "classroom_id": classroom_id}
    return render(request, "vocab_trainer/quiz/for_admin/textbook_not_found.html", ctx, status=status)


def error_handling_to_chapter_not_found(request, *, status=404):
    student_id = request.POST.get("target_student_id") or request.GET.get("target_student_id")
    classroom_id = request.POST.get("classroom_id") or request.GET.get("classroom_id")
    ctx = {"student_id": student_id, "classroom_id": classroom_id}
    return render(request, "vocab_trainer/quiz/for_admin/chapter_not_found.html", ctx, status=status)


def error_handling_to_quiz_type_select(request, student, classroom_id, *, status=200):
    ctx = build_quiz_type_select_context(student, classroom_id)
    ctx["error_message"] = "復習対象の単語が見つかりませんでした。"
    return render(request, "vocab_trainer/quiz/for_admin/quiz_type_select.html", ctx, status=status)


@login_required
@user_passes_test(is_admin_or_teacher)
def quiz_review_with_admin(request):
    """ 管理者・講師用：復習クイズ """
    if request.method != 'POST':
        return redirect("vocab_trainer:quiz_type_select_with_admin")

    quiz_mode = 'review'
    step = "start"
    logctx = {
        "user_id": getattr(request.user, "id", None),
        "role": getattr(request.user, "role", None),
    }

    try:
        step = "get_student"
        student_id_from_input = request.POST.get("target_student_id")
        if not student_id_from_input:
            logctx["reason"] = "missing_target_student_id"
            logger.warning("生徒を正しく取得できません。 step=%s ctx=%s", step, logctx)
            return error_handling_to_quiz_error(request)
        logctx["student_id_from_input"] = student_id_from_input
        student = get_accessible_student_by_uuid_or_404(request.user, student_id_from_input)
        logctx["student_id_from_db"] = student.id

        step = "textbook_existence_check"
        if not student.textbook_id:
            logger.warning("教科書が存在していません。 step=%s ctx=%s", step, logctx)
            return error_handling_to_textbook_not_found(request, status=400)

        step = "get_classroom_id"
        classroom_id = request.POST.get('classroom_id') or request.GET.get("classroom_id")
        if not classroom_id:
            logger.warning("教室IDが取得できません。step=%s ctx=%s", step, logctx)
            return error_handling_to_quiz_error(request)
        
        step = "get_and_decide_context"
        word_meaning_context = pick_review_context_by_softmax(student)
        if word_meaning_context is None:
            logger.warning(
                "復習用のWordMeaningContextが選定できませんでした。(step: %s, logctx: %s)", step, logctx
            )
            return error_handling_to_quiz_type_select(request, student, classroom_id)
        
        logctx["word_meaning_context_id"] = word_meaning_context.id
        question_relation = word_meaning_context.relation
        logctx["question_relation_id"] = question_relation.id

        # ✅ クイズタイプのランダム選択
        step = "decide_quiz_type"
        quiz_type = random.choice(['jp_to_en', 'en_to_jp'])
        logctx["quiz_type"] = quiz_type

        # ✅ 4択の選択肢を取得
        step = "get_four_choices"
        choices = get_choices(question_relation, quiz_type)
        if len(choices) < 4:
            logger.warning(
                "選択肢が正しく取得できませんでした。(step: %s, logctx: %s)", step, logctx
            )
            return error_handling_to_quiz_error(request)

        step = "decide_quiz_type"
        if quiz_type == 'jp_to_en':
            question_text = question_relation.japanese_meaning.meaning
            correct_answer = question_relation.english_word.word
        else:
            question_text = question_relation.english_word.word
            correct_answer = question_relation.japanese_meaning.meaning

        context = {
            'choices': choices,
            'quiz_mode': quiz_mode,
            'quiz_type': quiz_type,
            'question_text': question_text,
            'correct_answer': correct_answer,
            'student': student,
            'classroom_id': classroom_id,
            'context': word_meaning_context
        }

        return render(request, 'vocab_trainer/quiz/for_admin/quiz.html', context)

    except Http404:
        logger.warning("想定されたクイズ出題の失敗 step=%s ctx=%s", step, logctx)
        return error_handling_to_quiz_error(request)

    except Exception:
        logger.exception("想定されていないクイズ出題の失敗 step=%s ctx=%s", step, logctx)
        return error_handling_to_quiz_error(request, status=500)
    
    finally:
        logger.debug("step: %s, logctx: %s", step, logctx)
