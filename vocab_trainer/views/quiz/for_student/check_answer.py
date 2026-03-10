import logging
from urllib.parse import urlencode

from django.shortcuts import redirect, get_object_or_404, render
from django.http import JsonResponse, Http404
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction


from vocab_trainer.models import (
    EnglishWord, JapaneseMeaning, WordMeaningRelation, QuizResult,
    StudentContextProgress, WordMeaningContext, WordMeaningRelationDifficulty
)
from processors.example_sentence_processor import ExampleSentenceProcessor

logger = logging.getLogger(__name__)

def is_student(user):
    """生徒のみアクセス可能"""
    return user.role == "student"

def is_json_request(request) -> bool:
    """
    このリクエストが JSON レスポンスを期待しているかどうかを判定する。

    判定基準:
    - fetch / Ajax 由来 (X-Requested-With)
    - Accept ヘッダに application/json を含む
    """
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return True

    accept = request.headers.get("accept", "")
    if "application/json" in accept.lower():
        return True

    return False

def error_handling(request, *, status=404, code="QUIZ_FAILED"):
    if is_json_request(request):
        return JsonResponse(
            {"error": {"code": code, "message": "クイズ出題・採点に失敗しました。"}},
            status=status
        )

    ctx = {}
    return render(request, "vocab_trainer/quiz/for_student/quiz_error.html", ctx, status=status)

def check_existence_of_required_information(request):
    """POSTにこの後必要な情報が詰まっているかを確認する
    
    Args:
        request: 情報が格納されているリクエスト
    
    Returns:
        missing (list): 不足している情報群
    """
    required = ["selected_answer", "correct_answer", "question_text", "quiz_type", "quiz_mode", "context_id"]
    missing = [k for k in required if not request.POST.get(k)]
    return missing



@login_required
@user_passes_test(is_student)
def check_answer_for_student(request):
    """ クイズの回答をチェックし、進捗・難易度を更新 """
    if request.method != "POST":
        url = reverse("vocab_trainer:quiz_type_select_for_student")
        return redirect(url)


    step = "start"
    logctx = {}
    missing = check_existence_of_required_information(request)
    if missing:
        logger.warning(
            "処理に必要な情報がPOST中に存在していません。(missing: %s, step: %s)", missing, step
        )
        return error_handling(request, status=400, code="MISSING_PARAM")
    
    try:
        student = request.user.get_role_object()
        if student is None:
            logger.warning(
                "対象生徒が存在しません。 (user.id: %s)", request.user.id
            )
            return error_handling(request, status=404)
        logctx["student_id"] = str(getattr(student, "id", ""))

        step = "read_params"
        selected_answer = request.POST.get('selected_answer')
        logctx["selected_answer"] = selected_answer
        correct_answer = request.POST.get('correct_answer')
        logctx["correct_answer"] = correct_answer
        word_text = request.POST.get('question_text')
        logctx["word_text"] = word_text
        quiz_type = request.POST.get('quiz_type')
        logctx["quiz_type"] = quiz_type
        quiz_mode = request.POST.get('quiz_mode')
        logctx["quiz_mode"] = quiz_mode

        # ✅ 日本語 → 英語 or 英語 → 日本語の出題判定
        step = "get_relation"
        if quiz_type == 'jp_to_en':
            japanese_meaning = get_object_or_404(JapaneseMeaning, meaning=word_text)
            relation = get_object_or_404(WordMeaningRelation, japanese_meaning=japanese_meaning, english_word__word=correct_answer)
        elif quiz_type == 'en_to_jp':
            english_word = get_object_or_404(EnglishWord, word=word_text)
            relation = get_object_or_404(WordMeaningRelation, english_word=english_word, japanese_meaning__meaning=correct_answer)
        else:
            logger.warning(
                "不正なクイズタイプが選択されました。(step: %s, logctx: %s, quiz_type: %s)", step, logctx, quiz_type,
                )
            return error_handling(request, status=400, code="INVALID_QUIZ_TYPE")  # bad request
        logctx["relation_id"] = str(getattr(relation, "id", ""))

        step = "judge"
        is_correct = (selected_answer == correct_answer)
        logctx["is_correct"] = is_correct
        
        step = "get_context"
        context_id = request.POST.get('context_id')
        logctx["context_id_from_input"] = context_id
        context = get_object_or_404(WordMeaningContext, pk=context_id)
        logctx["context_id_from_db"] = str(getattr(context, "id", ""))
        
        step = "context_existence_check"
        if not relation.contexts.filter(id=context.id).exists():
            logger.warning(
                "不正なコンテキストが検出されました。(context: %s, relation: %s, step: %s, logctx: %s)", context, relation, step, logctx
                )
            return error_handling(request, status=400, code="INVALID_CONTEXT")
        
        with transaction.atomic():
            step = "save_quiz_result"
            QuizResult.objects.create(
                student=student,
                context=context,
                is_correct=is_correct
            )
            step = "update_difficulty_and_correct_count"
            relation_difficulty, created = WordMeaningRelationDifficulty.objects.get_or_create(
                relation=relation
            )
            relation_difficulty.total_count += 1
            if is_correct:
                relation_difficulty.correct_count += 1
            relation_difficulty.update_difficulty()

            step = "update_progress"
            progress, created = StudentContextProgress.objects.get_or_create(
                student=student,
                context=context
            )
            progress.update_progress(is_correct)

        step = "get_example_sentence"
        example_sentence = relation.example_sentence
        
        try:
            if not example_sentence:
                example_processor = ExampleSentenceProcessor()
                example_sentence = example_processor.generate_example_sentence(
                    word=relation.english_word.word,
                    japanese_meaning=relation.japanese_meaning,
                    part_of_speech=", ".join([p.part_of_speech.display_name for p in relation.parts_of_speech.all()])
                )
        except Exception:
            logger.exception(
                "例文生成処理に失敗しましたが、処理を継続します。(step: %s, logctx: %s)", step, logctx
                )
            example_sentence = ""

        # ✅ クイズ終了後の遷移先
        step = "next_url"
        if quiz_mode == 'all':
            next_url = reverse('vocab_trainer:quiz_all_for_student')
        elif quiz_mode == 'chapter':
            next_url = reverse('vocab_trainer:quiz_chapter_for_student')
        elif quiz_mode == 'review':
            next_url = reverse('vocab_trainer:quiz_review_for_student')
        else:
            next_url = reverse('vocab_trainer:quiz_type_select_for_student')

        step = "response"
        return JsonResponse({
            'is_correct': is_correct,
            'correct_answer': correct_answer,
            'part_of_speech': ", ".join([p.part_of_speech.display_name for p in relation.parts_of_speech.all()]),
            'example_sentence': example_sentence,
            'next_url': next_url
        })
        
    except Http404:
        # 想定内: 可視範囲外 / データ不整合 / 改ざん入力など
        logger.warning("quiz failed (Http404) step=%s ctx=%s", step, logctx)
        return error_handling(request)

    except Exception:
        # 想定外: バグ・外部障害等（スタックトレース必須）
        logger.exception("quiz crashed (unexpected) step=%s ctx=%s", step, logctx)
        return error_handling(request, status=500)

