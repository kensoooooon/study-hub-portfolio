"""長文問題のビュー

# 設計の特徴
Post-Redirect-Get パターン（PRG）に基づき、
クイズ選択画面(POST)→クイズごとの処理→画面表示へGETでリダイレクトを行う

# 各関数・クラス
- quiz_type_select_with_admin/quiz_type_select_for_student
    クイズ選択画面の表示を行う。
    想定されているクイズのタイプは、new(新規長文＋新規問題), reuse_question(既存長文＋新規問題), reuse_all(既存長文＋既存問題)

- AdminReadingQuizDispatcherView/StudentReadingQuizDispatcherView
    選択されたクイズタイプに応じた処理を実行。
    長文と問題の組み合わせは、passage_idとbatch_idを渡すことで、間接的に管理

- AdminReadingQuizSolveView/StudentReadingQuizSolveView
    渡されたpassage_idとbatch_idから、問題と選択肢の生成、および解答画面の処理を行う
"""
from django.shortcuts import render, redirect
from django.views import View
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError


from vocab_trainer.models import StudentContextProgress
from vocab_trainer.services.student_availability import has_vocab_progress
from read_trainer.utils.quiz_generation import (
    generate_and_save_passage_with_questions,
    append_questions_to_existing_passage,
    get_latest_batch_for_passage,
    generate_eiken_passage_with_questions,
    append_questions_to_existing_eiken_passage,
)
from read_trainer.utils.quiz_scoring import process_reading_answers
from read_trainer.services import softmax_permute_contexts_from_progresses
from read_trainer.utils.quiz_selection import select_passages_for_student
from read_trainer.access_check.student_access_check import student_access_check
from read_trainer.access_check.passage_access_check import passage_access_check
from read_trainer.models import ReadingPassage
from accounts.models import BaseUser
from read_trainer.utils.get_batch_id import get_and_validate_batch_id_from_request


import logging

logger = logging.getLogger(__name__)



def is_student(user: BaseUser) -> bool:
    """ユーザーが生徒ロール

    Args:
        user (BaseUser): 判定対象

    Returns:
        bool: 生徒であるか否か
    """
    return getattr(user, "role", None) == "student"


VALID_EIKEN_LEVELS = {value for value, _ in ReadingPassage.EIKEN_LEVEL_CHOICES}

def is_valid_eiken_level(eiken_level: str | None) -> bool:
    """英検のレベル指定が妥当かどうかのチェック

    Args:
        eiken_level (str | None): 検証対象の英検レベル

    Returns:
        bool: 妥当であるか否か
    """
    return eiken_level in VALID_EIKEN_LEVELS



def quiz_type_select_for_student(request):
    """生徒用のクイズ選択を表示"""
    if not request.user.is_authenticated:
        return redirect("accounts_auth:login")
    if not is_student(request.user):
        ctx = {
            "user_id": request.user.id,
            "user_role": getattr(request.user, "role", None)
        }
        logger.warning(
            "生徒用クイズ選択に対して、異なるロールのユーザーからアクセスがありました。",
            extra=ctx
        )
        raise PermissionDenied("この機能にアクセスできません。")
    student_id = request.user.id
    student = student_access_check(request.user, student_id)
    if not has_vocab_progress(student):
        return render(request, "read_trainer/for_student/no_vocab_available.html", {})
    progresses_of_recommended_passage, has_reading_passages = select_passages_for_student(student, "textbook")
    now = timezone.now()
    for p in progresses_of_recommended_passage:
        p.calculated_priority = p.get_review_priority(now)
    context = {
        'student': student,
        'has_reading_passages': has_reading_passages,
        'progresses_of_recommended_passage': progresses_of_recommended_passage,
    }
    return render(request, 'read_trainer/for_student/quiz_type_select.html', context)


def eiken_quiz_type_select_for_student(request):
    """生徒用のクイズ選択を表示"""
    if not request.user.is_authenticated:
        return redirect("accounts_auth:login")
    if not is_student(request.user):
        ctx = {
            "user_id": request.user.id,
            "user_role": getattr(request.user, "role", None)
        }
        logger.warning(
            "生徒用クイズ選択に対して、異なるロールのユーザーからアクセスがありました。",
            extra=ctx
        )
        raise PermissionDenied("この機能にアクセスできません。")
    student_id = request.user.id
    student = student_access_check(request.user, student_id)
    if not has_vocab_progress(student):
        return render(request, "read_trainer/for_student/no_vocab_available.html", {})
    progresses_of_recommended_passage, has_reading_passages = select_passages_for_student(student, "eiken")
    now = timezone.now()
    for p in progresses_of_recommended_passage:
        p.calculated_priority = p.get_review_priority(now)
    context = {
        'student': student,
        'has_reading_passages': has_reading_passages,
        'progresses_of_recommended_passage': progresses_of_recommended_passage,
    }
    return render(request, 'read_trainer/for_student/eiken_quiz_type_select.html', context)


class StudentReadingQuizDispatcherView(View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts_auth:login")
        if not is_student(request.user):
            ctx = {
                "user_id": request.user.id,
                "user_role": getattr(request.user, "role", None)
            }
            logger.warning(
                "生徒用クイズ出題処理に対して、異なるロールのユーザーからアクセスがありました。",
                extra=ctx
            )
            raise PermissionDenied("この機能にアクセスできません。")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        quiz_type = request.POST.get("quiz_type")
        student_id = request.user.id
        student = student_access_check(request.user, student_id)
        eiken_level = request.POST.get("eiken_level")

        if quiz_type is None:
            logger.error("クイズタイプが指定されていません。")
            return render(request, 'read_trainer/for_student/generation_failed.html', {"error_message": "クイズタイプが指定されていません。"})
        
        if quiz_type == "new":
            progresses = StudentContextProgress.objects.with_active_student().filter(
                student=student,
                total_count__gt=0
            ).select_related("context")

            sorted_contexts = softmax_permute_contexts_from_progresses(list(progresses))
            if not sorted_contexts:
                logger.warning("利用できる語彙が存在しません。(student: %s)", student)
                return render(request, "read_trainer/for_student/no_vocab_available.html", {})
            try:
                passage, batch_id = generate_and_save_passage_with_questions(student, sorted_contexts)
            except Exception:
                logger.exception("新規長文問題の生成に失敗しました。(student: %s)", student)
                return render(request, 'read_trainer/for_student/generation_failed.html', {
                    "error_message": "新規長文問題の生成に失敗しました。"
                })

        elif quiz_type == "reuse_questions":
            passage_id = request.POST.get("passage_id")
            # passage = get_object_or_404(ReadingPassage, id=passage_id, created_by=student, source_type="textbook")
            passage = passage_access_check(request.user, passage_id, source_type="textbook", expected_student_id=student.id)
            progresses = StudentContextProgress.objects.with_active_student().filter(
                student=student,
                total_count__gt=0
            ).select_related("context")

            sorted_contexts = softmax_permute_contexts_from_progresses(list(progresses))
            if not sorted_contexts:
                logger.warning("利用できる語彙が存在しません。(student: %s)", student)
                return render(request, "read_trainer/for_student/no_vocab_available.html", {})
            try:
                passage, batch_id = append_questions_to_existing_passage(student, passage, sorted_contexts)
            except Exception:
                logger.exception("再利用長文問題の生成に失敗しました。")
                return render(request, 'read_trainer/for_student/generation_failed.html', {
                    "error_message": "再利用長文問題の生成に失敗しました。"
                })

        elif quiz_type == "reuse_all":
            passage_id = request.POST.get("passage_id")
            # passage = get_object_or_404(ReadingPassage, id=passage_id, created_by=student, source_type="textbook")
            passage = passage_access_check(request.user, passage_id, source_type="textbook", expected_student_id=student.id)
            batch_id = get_latest_batch_for_passage(passage)
            if (batch_id is None) or (not str(batch_id).isdigit()):
                logger.error("batch_idが存在しません。(passage_id: %s, batch_id: %s)",
                            passage_id, batch_id)
                return render(request, 'read_trainer/for_student/no_passage_available.html', {"error_message": "利用できる問題バージョンが存在しません。"})
    
        elif quiz_type == "eiken_new":
            if not is_valid_eiken_level(eiken_level):
                logger.warning("英検レベルが不正です。(eiken_level=%s)", eiken_level)
                return render(request, "read_trainer/for_student/generation_failed.html", {
                    "error_message": "英検レベルが不正です。"
                })
            progresses = StudentContextProgress.objects.with_active_student().filter(
                student=student,
                total_count__gt=0
            ).select_related("context")

            sorted_contexts = softmax_permute_contexts_from_progresses(list(progresses))
            if not sorted_contexts:
                logger.warning("利用できる語彙が存在しません。(student: %s)", student)
                return render(request, "read_trainer/for_student/no_vocab_available.html", {})
            
            try:
                passage, batch_id = generate_eiken_passage_with_questions(student, eiken_level, sorted_contexts)
            except Exception:
                logger.exception("新規英検問題の生成に失敗しました。")
                return render(request, 'read_trainer/for_student/generation_failed.html', {
                    "error_message": "新規英検問題の生成に失敗しました。"
                })

        elif quiz_type == "eiken_reuse_questions":
            if not is_valid_eiken_level(eiken_level):
                logger.warning("英検レベルが不正です。(eiken_level=%s)", eiken_level)
                return render(request, "read_trainer/for_student/generation_failed.html", {
                    "error_message": "英検レベルが不正です。"
                })
            passage_id = request.POST.get("passage_id")            
            # passage = get_object_or_404(ReadingPassage, id=passage_id, created_by=student, source_type="eiken")
            passage = passage_access_check(request.user, passage_id, source_type="eiken", expected_student_id=student.id)

            progresses = StudentContextProgress.objects.with_active_student().filter(
                student=student,
                total_count__gt=0
            ).select_related("context")

            sorted_contexts = softmax_permute_contexts_from_progresses(list(progresses))
            if not sorted_contexts:
                logger.warning("利用できる語彙が存在しません。(student: %s)", student)
                return render(request, "read_trainer/for_student/no_vocab_available.html", {})
            try:
                passage, batch_id = append_questions_to_existing_eiken_passage(student, passage, eiken_level, sorted_contexts)
            except Exception:
                logger.exception("英検再利用問題の生成に失敗しました。")
                return render(request, 'read_trainer/for_student/generation_failed.html', {
                    "error_message": "英検再利用問題の再生成に失敗しました。"
                })
                
        elif quiz_type == "eiken_reuse_all":
            passage_id = request.POST.get("passage_id")            
            # passage = get_object_or_404(ReadingPassage, id=passage_id, created_by=student, source_type="eiken")
            passage = passage_access_check(request.user, passage_id, source_type="eiken", expected_student_id=student.id)
            batch_id = get_latest_batch_for_passage(passage)
            if (batch_id is None) or (not str(batch_id).isdigit()):
                logger.error("batch_idが存在しません。(passage_id: %s, batch_id: %s)",
                            passage_id, batch_id)
                return render(request, 'read_trainer/for_student/no_passage_available.html', {"error_message": "利用できる問題バージョンが存在しません。"})

        else:
            logger.error("対応していない出題タイプが選択されました。(quiz_type: %s)", quiz_type)
            return render(request, 'read_trainer/for_student/generation_failed.html', {"error_message": "不明な出題タイプです。"})
        
        if "eiken" in quiz_type:
            is_eiken = 1
        else:
            is_eiken = 0

        return redirect(
            f"{reverse('read_trainer:student_solve', args=[passage.id])}?&batch_id={batch_id}&is_eiken={is_eiken}"
        )

class StudentReadingQuizSolveView(View):
    """クイズの回答画面、および結果画面の表示(生徒用)"""
    template_solve = "read_trainer/for_student/solve.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts_auth:login")
        if not is_student(request.user):
            ctx = {
                "user_id": request.user.id,
                "user_role": getattr(request.user, "role", None)
            }
            logger.warning(
                "生徒用クイズ出題処理に対して、異なるロールのユーザーからアクセスがありました。",
                extra=ctx
            )
            raise PermissionDenied("この機能にアクセスできません。")
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
            return render(request, "read_trainer/for_student/generation_failed.html", {
                "error_message": "バッチIDが不正です。"
            })

        questions = passage.questions.filter(batch_id=batch_id)

        if not questions.exists():
            return render(request, "read_trainer/for_student/generation_failed.html", {
                "error_message": "指定されたバッチIDの問題が存在しません。"
            })

        context = {
            "passage": passage,
            "student": passage.created_by,
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
            return render(request, "read_trainer/for_student/scoring_failed.html", {
                "error_message": "バッチIDが不正です。"
            })

        questions = passage.questions.filter(batch_id=batch_id)
        if not questions.exists():
            logger.error("長文に紐づけられた問題が存在しません。(questions: %s, batch_id: %s, passage_id: %s)", questions, batch_id, passage.id)
            return render(request, "read_trainer/for_student/scoring_failed.html", {
                "error_message": "指定されたバッチIDの問題が存在しません。"
            })
            
        try:
            results = process_reading_answers(student, passage, questions, request.POST)
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
                "read_trainer/for_student/scoring_failed.html",
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
                "read_trainer/for_student/scoring_failed.html",
                {"error_message": "解答処理中に予期しないエラーが発生しました。"},
            )

        request.session["read_quiz_result"] = {
            "passage_id": passage.id,
            "student_id": str(student.id),
            "is_eiken": is_eiken,
            "audio_file_names": audio_file_names,
            "batch_id": batch_id,
            # ここで結果全体をシリアライズしてもよいが、必要最低限を保存
            "result_data": [
                {
                    "question_id": r["question"].id,
                    "selected_option": r["selected_option"],
                    "is_correct": r["is_correct"],
                }
                for r in results
            ],
        }
        url = reverse("read_trainer:student_result")
        return redirect(f"{url}?is_eiken={'1' if is_eiken else '0'}")


@require_GET
def student_result_view(request):
    if not request.user.is_authenticated:
        return redirect("accounts_auth:login")
    if not is_student(request.user):
        ctx = {
            "user_id": request.user.id,
            "user_role": getattr(request.user, "role", None)
        }
        logger.warning(
            "生徒用クイズ結果表示に対して、異なるロールのユーザーからアクセスがありました。",
            extra=ctx
        )
        raise PermissionDenied("この機能にアクセスできません。")
    data = request.session.pop("read_quiz_result", None)
    if not data:
        is_eiken = request.GET.get("is_eiken") in ("1", "true", "True")
        if is_eiken:
            return redirect("read_trainer:eiken_quiz_type_select_for_student")
        return redirect("read_trainer:quiz_type_select_for_student")
    
    student = student_access_check(request.user, data["student_id"])
    is_eiken = data["is_eiken"]
    source_type = "eiken" if is_eiken else "textbook"
    # passage = get_object_or_404(ReadingPassage.objects.visible_to(request.user), pk=data["passage_id"])
    passage = passage_access_check(request.user, data["passage_id"], expected_student_id=student.id, source_type=source_type)

    batch_id = data.get("batch_id")
    questions = passage.questions.filter(batch_id=batch_id)

    full_results = []
    for q in questions:
        selected = next(
            (
                r["selected_option"]
                for r in data["result_data"]
                if int(r["question_id"]) == q.id
            ),
            None,
        )
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

    return render(request, "read_trainer/for_student/result.html", context)
