import random
import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse
from django.http import Http404


from vocab_trainer.services import get_choices, pick_review_context_by_softmax

logger = logging.getLogger(__name__)


def is_student(user):
    """生徒のアクセスのみ許可する"""
    return user.role == "student"


def error_handling_to_quiz_error(request, *, status=404):
    ctx = {}
    return render(request, "vocab_trainer/quiz/for_student/quiz_error.html", ctx, status=status)


def error_handling_to_quiz_type_select(request, error_message=None):
    """
    クイズが成立しないが、不正とまでは言えない場合に利用し、ユーザーに選択し直してもらう
    """
    if error_message is not None:
        messages.error(request, error_message)
    url = reverse("vocab_trainer:quiz_type_select_for_student")
    return redirect(url)



@login_required
@user_passes_test(is_student)
def quiz_review_for_student(request):
    """ 復習用のクイズ """
    if request.method != "POST":
        logger.warning(
            "POST以外の形式でリクエストされました。(request.method: %s)", request.method
        )
        error_message = "不正なリクエストです。"
        return error_handling_to_quiz_type_select(request, error_message)


    quiz_mode = 'review'
    step = "start"
    logctx = {
        "user_id": getattr(request.user, "id", None),
        "role": getattr(request.user, "role", None),
    }
    
    try:
        step = "get_student"
        student = request.user.get_role_object()
        if not student:
            logger.warning(
                "対象となる生徒が存在しません。(user.id: %s)", request.user.id
            )
            return error_handling_to_quiz_error(request, status=404)
        logctx["student_id"] = str(getattr(student, "id", ""))

        step = "textbook_existence_check"
        if not student.textbook_id:
            logger.warning("教科書が存在していません。 step=%s ctx=%s", step, logctx)
            error_message = "教科書が未登録のため、クイズは利用できません。"
            return error_handling_to_quiz_type_select(request, error_message)

        step = "get_and_decide_context"
        word_meaning_context = pick_review_context_by_softmax(student)
        if word_meaning_context is None:
            logger.warning(
                "復習用のWordMeaningContextが選定できませんでした。(step: %s, logctx: %s)", step, logctx
            )
            error_message = "復習用の語彙が存在しません。"
            return error_handling_to_quiz_type_select(request, error_message)
        
        logctx["word_meaning_context_id"] = word_meaning_context.id
        question_relation = word_meaning_context.relation
        logctx["question_relation_id"] = question_relation.id
        
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
            'context': word_meaning_context
        }
        return render(request, 'vocab_trainer/quiz/for_student/quiz.html', context)

    except Http404:
        logger.warning("想定されたクイズ出題の失敗 step=%s ctx=%s", step, logctx)
        return error_handling_to_quiz_error(request)

    except Exception:
        logger.exception("想定されていないクイズ出題の失敗 step=%s ctx=%s", step, logctx)
        return error_handling_to_quiz_error(request, status=500)

    finally:
        logger.debug("step: %s, logctx: %s", step, logctx)
