import random
import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404
from django.contrib import messages
from django.urls import reverse

from vocab_trainer.services import get_choices, pick_quiz_context_by_ratio
from vocab_trainer.models import WordMeaningContext, Chapter

logger = logging.getLogger(__name__)

def is_student(user):
    """生徒のみアクセス可能"""
    return user.role == "student"


def error_handling_to_chapter_not_found(request, *, status=404):
    ctx = {}
    return render(request, "vocab_trainer/quiz/for_student/chapter_not_found.html", ctx, status=status)

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
def quiz_chapter_for_student(request):
    """ 特定のユニットから出題するクイズ（選択式） """
    if request.method != "POST":
        logger.warning(
            "POST以外の形式でリクエストされました。(request.method: %s)", request.method
        )
        error_message = "不正なリクエストです。"
        return error_handling_to_quiz_type_select(request, error_message)
    
    step = "start"
    quiz_mode = "chapter"
    logctx = {
        "user_id": str(getattr(request.user, "id", None)),
        "role": str(getattr(request.user, "role", None))
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
        
        step = "get_textbook"
        textbook = student.textbook
        if not textbook:
            logger.warning(
                "該当する教科書が存在していません。(step: %s, logctx: %s)", step, logctx
            )
            return error_handling_to_textbook_not_found(request, status=400)
        
        # ✅ チャプター選択を `POST` で取得
        step = "get_chapters"
        chapter_ids = request.POST.getlist('chapter_ids')
        if not chapter_ids:
            logger.warning(
                "チャプターが存在していません。step = %s, ctx = %s", step, logctx)
            return error_handling_to_chapter_not_found(request)
        logctx["chapter_ids"] = chapter_ids
        
        step = "validate_chapters"
        valid_chapter_count = Chapter.objects.filter(textbook=textbook, id__in=chapter_ids).count()
        if valid_chapter_count != len(chapter_ids):
            logger.warning("chapter_ids mismatch step=%s ctx=%s", step, logctx)
            return error_handling_to_quiz_type_select(request, "不正なリクエストです。")

        # ✅ 出題候補の取得
        step = "decide_base_candidates"
        # ✅ 出題候補の取得（選択チャプター内の context を母集団にする）
        base_contexts = WordMeaningContext.objects.filter(
            chapter__textbook=textbook,
            chapter__id__in=chapter_ids,
        ).select_related(
            "relation",
            "relation__english_word",
            "relation__japanese_meaning",
            "chapter",
        )

        step = "pick_candidates"
        picked = pick_quiz_context_by_ratio(
            student=student,
            base_contexts=base_contexts,
            ratio=(6, 3, 1),
            high_top_n=200,  # 偏りが気になるなら増やす
        )

        if not picked:
            logger.warning(
                "出題用のWordMeaningContextが取得できませんでした。(step: %s, logctx: %s)", step, logctx
                )
            error_message = "対象の語彙が存在しません。"
            return error_handling_to_quiz_type_select(request, error_message)
        
        # ✅ ランダムで1問確定（contextに統一）
        step = "decide_context"
        bucket = picked.bucket
        logctx["bucket"] = bucket
        word_meaning_context = picked.context
        logctx["word_meaning_context_id"] = word_meaning_context.id
        question_relation = word_meaning_context.relation
        logctx["question_relation_id"] = question_relation.id


        step = "decide_quiz_type"
        quiz_type = random.choice(['jp_to_en', 'en_to_jp'])

        step = "get_choices"
        choices = get_choices(question_relation, quiz_type)

        step = "decide_question_text_and_correct_answer"
        if quiz_type == 'jp_to_en':
            question_text = question_relation.japanese_meaning.meaning
            correct_answer = question_relation.english_word.word
        else:
            question_text = question_relation.english_word.word
            correct_answer = question_relation.japanese_meaning.meaning

        context = {
            'chapter_ids': chapter_ids,
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