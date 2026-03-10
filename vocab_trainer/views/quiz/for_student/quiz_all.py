import random
import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse
from django.http import Http404

from vocab_trainer.models import WordMeaningContext
from vocab_trainer.services import get_choices, pick_random_context

logger = logging.getLogger(__name__)


def is_student(user):
    """生徒のみアクセス可能"""
    return user.role == "student"


def error_handling_to_quiz_error(request, *, status=404):
    ctx = {}
    return render(request, "vocab_trainer/quiz/for_student/quiz_error.html", ctx, status=status)


def error_handling_to_textbook_not_found(request, *, status=404):
    ctx = {}
    return render(request, "vocab_trainer/quiz/for_student/textbook_not_found.html", ctx, status=status)

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
def quiz_all_for_student(request):
    """ 教科書全体から出題するクイズ """
    if request.method != "POST":
        logger.warning(
            "POST以外の形式でリクエストされました。(request.method: %s)", request.method
        )
        error_message = "不正なリクエストです。"
        return error_handling_to_quiz_type_select(request, error_message)
    
    step = "start"
    quiz_mode = "all"
    logctx = {
        "user_id": str(getattr(request.user, "id", None)),
        "role": str(getattr(request.user, "role", None))
    }
    
    try:
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
            return error_handling_to_textbook_not_found(request, status=400)


        # ✅ 生徒の教科書に含まれる語彙からランダム出題
        step = "pick_random_context"
        base_qs = WordMeaningContext.objects.filter(chapter__textbook_id=student.textbook_id)
        
        picked = pick_random_context(base_contexts=base_qs)
        if picked is None:
            logger.warning(
                "対象となるWordMeaningContextが存在しません。(step: %s, logctx: %s)", step, logctx
                )
            error_message = "対象の語彙が存在しません。"
            return error_handling_to_quiz_type_select(request, error_message)
        word_meaning_context = picked.context
        logctx["context_id"] = word_meaning_context.id
        question_relation = word_meaning_context.relation
        logctx["relation_id"] = question_relation.id
        bucket = picked.bucket
        logctx["bucket"] = bucket


        step = "decide_quiz_type"
        quiz_type = random.choice(['jp_to_en', 'en_to_jp'])
        logctx["quiz_type"] = quiz_type

        step = "get_four_choices"
        choices = get_choices(question_relation, quiz_type)

        step = "build_question"
        if quiz_type == 'jp_to_en':
            question_text = question_relation.japanese_meaning.meaning
            correct_answer = question_relation.english_word.word
        elif quiz_type == "en_to_jp":
            question_text = question_relation.english_word.word
            correct_answer = question_relation.japanese_meaning.meaning
        else:
            logger.warning(
                "不正なクイズタイプが選択されました。(step: %s, logctx: %s, quiz_type: %s)",step, logctx, quiz_type,
                )
            return error_handling_to_quiz_error(request, status=400)

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
