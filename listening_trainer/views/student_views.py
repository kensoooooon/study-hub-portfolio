import logging

from django.shortcuts import render, redirect
from django.views import View
from django.views.decorators.http import require_GET
from django.utils import timezone
from django.urls import reverse
from django.core.exceptions import PermissionDenied, ValidationError

from listening_trainer.access_check.student_access_check import (
    student_access_check,
    is_student,
)
from listening_trainer.access_check.passage_access_check import passage_access_check
from listening_trainer.utils.quiz_generation import (
    generate_and_save_passage_with_questions,
    append_questions_to_existing_passage,
    get_latest_batch_for_passage,
    generate_eiken_passage_with_questions,
    append_questions_to_existing_eiken_passage,
)
from listening_trainer.utils.quiz_scoring import process_listening_answers
from listening_trainer.utils.quiz_selection import select_passages_for_student
from listening_trainer.services import softmax_permute_contexts_from_progresses
from listening_trainer.models import ListeningPassage
from vocab_trainer.models import StudentContextProgress
from vocab_trainer.services.student_availability import has_vocab_progress
from listening_trainer.utils.get_batch_id import get_and_validate_batch_id_from_request

logger = logging.getLogger(__name__)

VALID_EIKEN_LEVELS = {value for value, _ in ListeningPassage.EIKEN_LEVEL_CHOICES}


def is_valid_eiken_level(eiken_level):
    return eiken_level in VALID_EIKEN_LEVELS


def quiz_type_select_for_student(request):
    """POST,Getの両方に対応したクイズタイプ選択画面"""
    if not request.user.is_authenticated:
        return redirect("accounts_auth:login")
    if not is_student(request.user):
        logger.warning(
            "生徒用クイズ選択画面ビューに不正なアクセスがありました。",
            extra={
                "user.id": request.user.id,
                "user.role": getattr(request.user, "role", None)
                }
        )
        raise PermissionDenied("この機能にアクセスできません。")
    student = student_access_check(request.user, request.user.id)
    if not has_vocab_progress(student):
        return render(request, "listening_trainer/for_student/no_vocab_available.html", {})
    progresses_of_recommended_passage, has_listening_passages = select_passages_for_student(student, "textbook")
    now = timezone.now()
    for p in progresses_of_recommended_passage:
        p.calculated_priority = p.get_review_priority(now)
    context = {
        'student': student,
        'has_listening_passages': has_listening_passages,
        'progresses_of_recommended_passage': progresses_of_recommended_passage,
    }
    return render(request, 'listening_trainer/for_student/quiz_type_select.html', context)


def eiken_quiz_type_select_for_student(request):
    """生徒用の英検クイズ選択を表示"""
    if not request.user.is_authenticated:
        return redirect("accounts_auth:login")
    if not is_student(request.user):
        logger.warning(
            "生徒用英検クイズ選択画面ビューに不正なアクセスがありました。",
            extra={
                "user.id": request.user.id,
                "user.role": getattr(request.user, "role", None)
                }
        )
        raise PermissionDenied("この機能にアクセスできません。")
    student = student_access_check(request.user, request.user.id)
    if not has_vocab_progress(student):
        return render(request, "listening_trainer/for_student/no_vocab_available.html", {})
    progresses_of_recommended_passage, has_listening_passages = select_passages_for_student(student, "eiken")
    now = timezone.now()
    for p in progresses_of_recommended_passage:
        p.calculated_priority = p.get_review_priority(now)
    context = {
        'student': student,
        'has_listening_passages': has_listening_passages,
        'progresses_of_recommended_passage': progresses_of_recommended_passage,
    }
    return render(request, 'listening_trainer/for_student/eiken_quiz_type_select.html', context)


class StudentListeningQuizDispatcherView(View):
    """選択されたクイズに必要な処理を実施し、クイズ解答画面へリダイレクト"""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts_auth:login")

        if not(is_student(request.user)):
            logger.warning(
                "生徒用クイズディスパッチャービューに不正なアクセスがありました。",
                extra={
                    "user.id": request.user.id,
                    "user.role": getattr(request.user, "role", None)
                    }
            )
            raise PermissionDenied("この機能にアクセスすることができません。")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        quiz_type = request.POST.get("quiz_type")
        student = student_access_check(request.user, request.user.id)
        eiken_level = request.POST.get("eiken_level")

        if quiz_type is None:
            logger.error("クイズタイプが指定されていません。")
            return render(request, 'listening_trainer/for_student/generation_failed.html', {"error_message": "クイズタイプが指定されていません。"})

        if quiz_type == "new":
            progresses = StudentContextProgress.objects.with_active_student().filter(
                student=student,
                total_count__gt=0
            ).select_related("context")

            sorted_contexts = softmax_permute_contexts_from_progresses(list(progresses))
            if not sorted_contexts:
                logger.warning("利用できる語彙が存在しません。(student: %s)", student)
                return render(request, "listening_trainer/for_student/no_vocab_available.html", {})
            try:
                passage, batch_id = generate_and_save_passage_with_questions(student, sorted_contexts)
            except Exception:
                logger.exception("新規リスニング問題の再生成に失敗しました。")
                return render(request, 'listening_trainer/for_student/generation_failed.html', {
                    "error_message": "新規リスニング問題の再生成に失敗しました。"
                })

        elif quiz_type == "reuse_questions":
            passage_id = request.POST.get("passage_id")
            passage = passage_access_check(request.user, passage_id, source_type="textbook", expected_student_id=student.id)
            progresses = StudentContextProgress.objects.with_active_student().filter(
                student=student,
                total_count__gt=0
            ).select_related("context")

            sorted_contexts = softmax_permute_contexts_from_progresses(list(progresses))
            if not sorted_contexts:
                logger.warning("利用できる語彙が存在しません。(student: %s)", student)
                return render(request, "listening_trainer/for_student/no_vocab_available.html", {})
            try:
                passage, batch_id = append_questions_to_existing_passage(student, passage, sorted_contexts)
            except Exception:
                logger.exception("再利用リスニング問題の生成に失敗しました。")
                return render(request, 'listening_trainer/for_student/generation_failed.html', {
                    "error_message": "再利用リスニング問題の生成に失敗しました。"
                })

        elif quiz_type == "reuse_all":
            passage_id = request.POST.get("passage_id")
            passage = passage_access_check(request.user, passage_id, source_type="textbook", expected_student_id=student.id)

            batch_id = get_latest_batch_for_passage(passage)
            if (batch_id is None) or (not str(batch_id).isdigit()):
                logger.error("batch_idが存在しません。(passage_id: %s, batch_id: %s)",
                            passage_id, batch_id)
                return render(request, 'listening_trainer/for_student/no_passage_available.html', {"error_message": "利用できる問題バージョンが存在しません。"})

        elif quiz_type == "eiken_new":
            if not is_valid_eiken_level(eiken_level):
                logger.warning("不正な英検レベルが指定されました。(student: %s, eiken_level: %s)", student, eiken_level)
                return render(request, 'listening_trainer/for_student/generation_failed.html', {
                    "error_message": "英検レベルが不正です。"
                })
            progresses = StudentContextProgress.objects.with_active_student().filter(
                student=student,
                total_count__gt=0
            ).select_related("context")

            sorted_contexts = softmax_permute_contexts_from_progresses(list(progresses))
            if not sorted_contexts:
                logger.warning("利用できる語彙が存在しません。(student: %s)", student)
                return render(request, "listening_trainer/for_student/no_vocab_available.html", {})
            try:
                passage, batch_id = generate_eiken_passage_with_questions(student, eiken_level, sorted_contexts)
            except Exception:
                logger.exception("新規英検用リスニング問題の再生成に失敗しました。")
                return render(request, 'listening_trainer/for_student/generation_failed.html', {
                    "error_message": "新規英検用リスニング問題の生成に失敗しました。"
                })

        elif quiz_type == "eiken_reuse_questions":
            if not is_valid_eiken_level(eiken_level):
                logger.warning("不正な英検レベルが指定されました。(student: %s, eiken_level: %s)", student, eiken_level)
                return render(request, 'listening_trainer/for_student/generation_failed.html', {
                    "error_message": "英検レベルが不正です。"
                })
            passage_id = request.POST.get("passage_id")
            passage = passage_access_check(request.user, passage_id, source_type="eiken", expected_student_id=student.id)

            progresses = StudentContextProgress.objects.with_active_student().filter(
                student=student,
                total_count__gt=0
            ).select_related("context")

            sorted_contexts = softmax_permute_contexts_from_progresses(list(progresses))
            if not sorted_contexts:
                logger.warning("利用できる語彙が存在しません。(student: %s)", student)
                return render(request, "listening_trainer/for_student/no_vocab_available.html", {})
            try:
                passage, batch_id = append_questions_to_existing_eiken_passage(student, passage, eiken_level, sorted_contexts)
            except Exception:
                logger.exception("英検再利用問題の生成に失敗しました。")
                return render(request, 'listening_trainer/for_student/generation_failed.html', {
                    "error_message": "英検再利用問題の再生成に失敗しました。"
                })

        elif quiz_type == "eiken_reuse_all":
            passage_id = request.POST.get("passage_id")
            passage = passage_access_check(request.user, passage_id, source_type="eiken", expected_student_id=student.id)

            batch_id = get_latest_batch_for_passage(passage)
            if (batch_id is None) or (not str(batch_id).isdigit()):
                logger.error("batch_idが存在しません。(passage_id: %s, batch_id: %s)",
                            passage_id, batch_id)
                return render(request, 'listening_trainer/for_student/no_passage_available.html', {"error_message": "利用できる問題バージョンが存在しません。"})

        else:
            logger.error("対応していない出題タイプが選択されました。(quiz_type: %s)", quiz_type)
            return render(request, 'listening_trainer/for_student/generation_failed.html', {"error_message": "不明な出題タイプです。"})

        if "eiken" in quiz_type:
            is_eiken = 1
        else:
            is_eiken = 0

        return redirect(
            f"{reverse('listening_trainer:student_solve', args=[passage.id])}?&batch_id={batch_id}&is_eiken={is_eiken}"
        )


class StudentListeningQuizSolveView(View):
    """クイズの回答画面、および結果画面の表示"""
    template_solve = "listening_trainer/for_student/solve.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts_auth:login")

        if not(is_student(request.user)):
            logger.warning(
                "生徒用英検クイズ表示・処理ビューに不正なアクセスがありました。",
                extra={
                    "user.id": request.user.id,
                    "user.role": getattr(request.user, "role", None)
                    }
            )
            raise PermissionDenied("この機能にアクセスすることができません。")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        is_eiken = request.GET.get("is_eiken") == "1"
        source_type = "eiken" if is_eiken else "textbook"
        student_id = request.user.id
        student = student_access_check(request.user, student_id)
        passage = passage_access_check(request.user, pk, source_type=source_type, expected_student_id=student.id)

        try:
            batch_id = get_and_validate_batch_id_from_request(request)
        except ValidationError:
            return render(request, "listening_trainer/for_student/scoring_failed.html", {
                "error_message": "バッチIDが不正です。"
            })

        questions = passage.questions.filter(batch_id=batch_id)

        if not questions.exists():
            return render(request, "listening_trainer/for_student/scoring_failed.html", {
                "error_message": "指定されたバッチIDの問題が存在しません。"
            })

        context = {
            "passage": passage,
            "student": student,
            "questions": questions,
            "batch_id": batch_id,
            "is_eiken": is_eiken
        }
        return render(request, self.template_solve, context)

    def post(self, request, pk):
        """
        ユーザーの解答をPOSTとして受けとり、解答画面にリダイレクトする
        """
        # passage = get_object_or_404(ReadingPassage, pk=pk)
        is_eiken = request.POST.get("is_eiken") == "1"
        source_type = "eiken" if is_eiken else "textbook"
        student = student_access_check(request.user, request.user.id)
        passage = passage_access_check(
            request.user,
            pk,
            source_type=source_type,
            expected_student_id=student.id,
        )
        audio_file_names = request.POST.get("audio_file_names", "")

        try:
            batch_id = get_and_validate_batch_id_from_request(request)
        except ValidationError:
            return render(request, "listening_trainer/for_student/scoring_failed.html", {
                "error_message": "バッチIDが不正です。"
            })

        questions = passage.questions.filter(batch_id=batch_id)
        if not questions.exists():
            logger.error("長文に紐づけられた問題が存在しません。(questions: %s, batch_id: %s, passage_id: %s)", questions, batch_id, passage.id)
            return render(request, "listening_trainer/for_student/scoring_failed.html", {
                "error_message": "指定されたバッチIDの問題が存在しません。"
            })
            
        try:
            results = process_listening_answers(student, passage, questions, request.POST)
        except ValueError as e:
            # 不正な選択肢 → 入力データの問題（400 系）
            logger.warning(
                "不正な選択肢が送信されました。(student_id=%s, passage_id=%s, error=%s)",
                student.id,
                passage.id,
                e,
            )
            return render(
                request,
                "listening_trainer/for_student/scoring_failed.html",
                {"error_message": "解答データが不正です。画面を再読み込みして、もう一度解答を送信してください。"},
            )
        except Exception:
            # 想定外のエラー → サーバ側の問題（500 系）、ただしユーザーには一般的メッセージ
            logger.exception(
                "解答処理中に予期せぬエラー発生。(student_id: %s, passage_id: %s)",
                student.id,
                passage.id,
            )
            return render(
                request,
                "listening_trainer/for_student/scoring_failed.html",
                {"error_message": "解答処理中に予期しないエラーが発生しました。"},
            )
    
        request.session["listening_quiz_result"] = {
            "passage_id": passage.id,
            "student_id": str(student.id),
            "is_eiken": is_eiken,
            "audio_file_names": audio_file_names,
            "batch_id": int(batch_id),
            "result_data": [
                {
                    "question_id": r["question"].id,
                    "selected_option": r["selected_option"],
                    "is_correct": r["is_correct"],
                }
                for r in results
            ],
        }
        url = reverse("listening_trainer:student_result")
        return redirect(f"{url}?is_eiken={'1' if is_eiken else '0'}")


@require_GET
def student_result_view(request):
    if not request.user.is_authenticated:
        return redirect("accounts_auth:login")
    if not(is_student(request.user)):
        logger.warning(
            "生徒用クイズ結果表示画面ビューに不正なアクセスがありました。",
            extra={
                "user.id": request.user.id,
                "user.role": getattr(request.user, "role", None)
                }
        )
        raise PermissionDenied("この機能にアクセスすることができません。")
    data = request.session.pop("listening_quiz_result", None)
    if not data:
        is_eiken = request.GET.get("is_eiken") in ("1", "true", "True")
        if is_eiken:
            return redirect("listening_trainer:eiken_quiz_type_select_for_student")
        else:
            return redirect("listening_trainer:quiz_type_select_for_student")

    student = student_access_check(request.user, data["student_id"])
    is_eiken = data["is_eiken"]
    source_type = "eiken" if is_eiken else "textbook"
    passage = passage_access_check(
        request.user,
        data["passage_id"],
        source_type=source_type,
        expected_student_id=student.id,
    )

    batch_id = data.get("batch_id")
    questions = passage.questions.filter(batch_id=batch_id)
    full_results = []

    for q in questions:
        selected = next((r["selected_option"] for r in data["result_data"] if int(r["question_id"]) == q.id), None)
        full_results.append({
            "question": q,
            "selected_option": selected,
            "is_correct": selected == q.correct_option,
            "correct_option": q.correct_option,
            "options": [
                ("A", q.option_a),
                ("B", q.option_b),
                ("C", q.option_c),
                ("D", q.option_d),
            ],
        })
    context = {
        "passage": passage,
        "student": student,
        "results": full_results,
        "is_eiken": is_eiken,
        "audio_file_names": data["audio_file_names"],
    }

    return render(request, "listening_trainer/for_student/result.html", context)
