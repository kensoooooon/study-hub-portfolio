from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404
from django.urls import reverse
from django.contrib import messages

from vocab_trainer.models import WordMeaningContext
from vocab_trainer.services import (
    get_choices,
    pick_random_context,
)
from vocab_trainer.access_policies import get_accessible_student_by_uuid_or_404

import random
import logging
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


def is_admin_or_teacher(user):
    return user.role in ["teacher", "classroom_administrator", "organization_administrator"]


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


def error_handling_to_quiz_type_select(request, error_message=None):
    """
    クイズが成立しないが、不正とまでは言えない場合に利用し、ユーザーに選択し直してもらう
    """
    if error_message is not None:
        messages.error(request, error_message)
    target_student_id = request.POST.get("target_student_id") or request.GET.get("target_student_id") or ""
    classroom_id = request.POST.get("classroom_id") or request.GET.get("classroom_id") or ""
    params = {
        "target_student_id": target_student_id,
        "classroom_id": classroom_id,
    }
    params = {k: v for k, v in params.items() if v}
    url = reverse("vocab_trainer:quiz_type_select_with_admin")
    return redirect(f"{url}?{urlencode(params)}" if params else url)


@login_required
@user_passes_test(is_admin_or_teacher)
def quiz_all_with_admin(request):
    """管理者・講師用：教科書全体から出題するクイズ（context起点）"""

    if request.method != "POST":
        logger.warning(
            "POST以外の形式でリクエストされました。(request.method: %s)", request.method
        )
        error_message = "不正なリクエストです。"
        return error_handling_to_quiz_type_select(request, error_message)

    step = "start"
    quiz_mode = "all"
    logctx = {
        "user_id": getattr(request.user, "id", None),
        "role": getattr(request.user, "role", None),
    }

    try:
        # -----------------------------
        # 1) student取得 & 教科書チェック
        # -----------------------------
        step = "get_student"
        student_id_from_input = request.POST.get("target_student_id")
        if not student_id_from_input:
            logctx["reason"] = "missing_target_student_id"
            logger.warning("対象の生徒が存在しません。 step=%s ctx=%s", "get_student", logctx)
            return error_handling_to_quiz_error(request, status=400)
        logctx["student_id_from_input"] = student_id_from_input
        student = get_accessible_student_by_uuid_or_404(request.user, student_id_from_input)
        logctx["student_id_from_db"] = student.id

        step = "textbook_existence_check"
        if not student.textbook_id:
            logger.warning("教科書が存在していません。 step=%s ctx=%s", step, logctx)
            return error_handling_to_textbook_not_found(request, status=400)

        # -----------------------------
        # 2) context からランダムに1件選ぶ（ORDER BY ? 回避）
        # -----------------------------
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

        # -----------------------------
        # 3) quiz_type決定 + 選択肢生成
        # -----------------------------
        step = "decide_quiz_type"
        quiz_type = random.choice(["jp_to_en", "en_to_jp"])
        logctx["quiz_type"] = quiz_type

        step = "get_four_choices"
        choices = get_choices(question_relation, quiz_type)

        step = "build_question"
        if quiz_type == "jp_to_en":
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

        classroom_id = request.POST.get("classroom_id")
        logctx["classroom_id"] = classroom_id

        context = {
            "choices": choices,
            "quiz_mode": quiz_mode,
            "quiz_type": quiz_type,
            "question_text": question_text,
            "correct_answer": correct_answer,
            "student": student,
            "classroom_id": classroom_id,
            "context": word_meaning_context,  # ←採点単位が最初から確定
        }
        return render(request, "vocab_trainer/quiz/for_admin/quiz.html", context)

    except Http404:
        logger.warning("想定されたクイズ出題の失敗 step=%s ctx=%s", step, logctx)
        return error_handling_to_quiz_error(request)

    except Exception:
        logger.exception("想定されていないクイズ出題の失敗 step=%s ctx=%s", step, logctx)
        return error_handling_to_quiz_error(request, status=500)

    finally:
        logger.debug("step: %s, logctx: %s", step, logctx)