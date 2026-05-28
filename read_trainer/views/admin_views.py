"""長文問題のビュー

# 設計の特徴
Post-Redirect-Get パターン（PRG）に基づき、
クイズ選択画面(POST)→クイズごとの処理→画面表示へGETでリダイレクトを行う

# 各関数・クラス
- quiz_type_select_with_admin
    クイズ選択画面の表示を行う。
    想定されているクイズのタイプは、new(新規長文＋新規問題), reuse_question(既存長文＋新規問題), reuse_all(既存長文＋既存問題)

- AdminReadingQuizDispatcherView
    選択されたクイズタイプに応じた処理を実行。
    長文と問題の組み合わせは、passage_idとbatch_idを渡すことで、間接的に管理

- AdminReadingQuizSolveView
    渡されたpassage_idとbatch_idから、問題と選択肢の生成、および解答画面の処理を行う
"""

from django.shortcuts import render, redirect
from django.views import View
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError


from vocab_trainer.models import StudentContextProgress
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
from vocab_trainer.services.student_availability import has_vocab_progress


import logging

logger = logging.getLogger(__name__)


VALID_EIKEN_LEVELS = {value for value, _ in ReadingPassage.EIKEN_LEVEL_CHOICES}


def is_valid_eiken_level(eiken_level: str | None) -> bool:
    """英検のレベル指定が妥当かどうかのチェック

    Args:
        eiken_level (str | None): 検証対象の英検レベル

    Returns:
        bool: 妥当であるか否か
    """
    return eiken_level in VALID_EIKEN_LEVELS


def is_admin_or_teacher(user: BaseUser) -> bool:
    """管理者か講師かを判定

    Args:
        user (BaseUser): 判定

    Returns:
        bool: 管理者や講師か否か
    """
    return getattr(user, "role", None) in ['teacher', 'classroom_administrator', 'organization_administrator']


def quiz_type_select_with_admin(request):
    """POST, GETの両方に対応したクイズタイプ選択画面"""
    if not request.user.is_authenticated:
        return redirect("accounts_auth:login")
    if not is_admin_or_teacher(request.user):
        ctx = {
            "user_id": request.user.id,
            "user_role": getattr(request.user, "role", None)
        }
        logger.warning(
            "管理者・講師用クイズ選択に対して、異なるロールのユーザーからアクセスがありました。",
            extra=ctx
        )
        raise PermissionDenied("この機能にアクセスできません。")
    classroom_id = request.GET.get('classroom_id') or request.POST.get('classroom_id') or ''
    target_student_id = request.GET.get('target_student_id') or request.POST.get('target_student_id')
    student = student_access_check(request.user, target_student_id)
    if not has_vocab_progress(student):
        return render(request, "read_trainer/for_admin/no_vocab_available.html", {})
    progresses_of_recommended_passage, has_reading_passages = select_passages_for_student(student, "textbook")
    now = timezone.now()
    # 一時的に動的な属性を追加する
    for p in progresses_of_recommended_passage:
        p.calculated_priority = p.get_review_priority(now)
    context = {
        'classroom_id': classroom_id,
        'student': student,
        'has_reading_passages': has_reading_passages,
        'progresses_of_recommended_passage': progresses_of_recommended_passage,
    }
    return render(request, 'read_trainer/for_admin/quiz_type_select.html', context)


def eiken_quiz_type_select_with_admin(request):
    """POST, GETの両方に対応した英検クイズタイプ選択画面"""
    if not request.user.is_authenticated:
        return redirect("accounts_auth:login")
    if not is_admin_or_teacher(request.user):
        ctx = {
            "user_id": request.user.id,
            "user_role": getattr(request.user, "role", None)
        }
        logger.warning(
            "管理者・講師用英検クイズ選択に対して、異なるロールのユーザーからアクセスがありました。",
            extra=ctx
        )
        raise PermissionDenied("この機能にアクセスできません。")
    classroom_id = request.GET.get('classroom_id') or request.POST.get('classroom_id') or ''
    target_student_id = request.GET.get('target_student_id') or request.POST.get('target_student_id')
    student = student_access_check(request.user, target_student_id)
    if not has_vocab_progress(student):
        return render(request, "read_trainer/for_admin/no_vocab_available.html", {})
    progresses_of_recommended_passage, has_reading_passages = select_passages_for_student(student, "eiken")
    now = timezone.now()
    # 一時的に動的な属性を追加する
    for p in progresses_of_recommended_passage:
        p.calculated_priority = p.get_review_priority(now)
    context = {
        'classroom_id': classroom_id,
        'student': student,
        'has_reading_passages': has_reading_passages,
        'progresses_of_recommended_passage': progresses_of_recommended_passage,
    }
    return render(request, 'read_trainer/for_admin/eiken_quiz_type_select.html', context)


class AdminReadingQuizDispatcherView(View):
    """選択されたクイズに必要な処理を行い、クイズ解答画面へリダイレクト"""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts_auth:login")
        if not is_admin_or_teacher(request.user):
            ctx = {
                "user_id": request.user.id,
                "user_role": getattr(request.user, "role", None)
            }
            logger.warning(
                "管理者・講師用クイズ出題処理に対して、異なるロールのユーザーからアクセスがありました。",
                extra=ctx
            )
            raise PermissionDenied("この機能にアクセスできません。")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        student_id = request.POST.get("target_student_id")
        classroom_id = request.POST.get("classroom_id")
        quiz_type = request.POST.get("quiz_type")
        passage_id = request.POST.get("passage_id")
        eiken_level = request.POST.get("eiken_level")

        if quiz_type is None:
            logger.error("クイズタイプが指定されていません。")
            return render(request, 'read_trainer/for_admin/generation_failed.html', {"error_message": "クイズタイプが指定されていません。"})

        student = student_access_check(request.user, student_id)

        if quiz_type == "new":
            progresses = StudentContextProgress.objects.with_active_student().filter(
                student=student,
                total_count__gt=0
            ).select_related("context")

            sorted_contexts = softmax_permute_contexts_from_progresses(list(progresses))
            if not sorted_contexts:
                return render(request, "read_trainer/for_admin/no_vocab_available.html", {})
            try:
                passage, batch_id = generate_and_save_passage_with_questions(student, sorted_contexts)
            except Exception:
                logger.exception("新規長文問題の生成に失敗しました。(student: %s)", student)
                return render(request, 'read_trainer/for_admin/generation_failed.html', {
                    "error_message": "新規長文問題の生成に失敗しました。"
                })

        elif quiz_type == "reuse_questions":
            passage = passage_access_check(request.user, passage_id, source_type="textbook", expected_student_id=student.id)
            progresses = StudentContextProgress.objects.with_active_student().filter(
                student=student,
                total_count__gt=0
            ).select_related("context")

            sorted_contexts = softmax_permute_contexts_from_progresses(list(progresses))
            if not sorted_contexts:
                logger.warning("利用できる語彙が存在しません。(student: %s)", student)
                return render(request, "read_trainer/for_admin/no_vocab_available.html", {})
            try:
                passage, batch_id = append_questions_to_existing_passage(student, passage, sorted_contexts)
            except Exception:
                logger.exception("再利用長文問題の生成に失敗しました。")
                return render(request, 'read_trainer/for_admin/generation_failed.html', {
                    "error_message": "再利用長文問題の生成に失敗しました。"
                })

        elif quiz_type == "reuse_all":
            passage = passage_access_check(request.user, passage_id, source_type="textbook", expected_student_id=student.id)
            batch_id = get_latest_batch_for_passage(passage)
            if (batch_id is None) or (not str(batch_id).isdigit()):
                logger.error("batch_idが存在しません。(passage_id: %s, batch_id: %s)",
                            passage_id, batch_id)
                return render(request, 'read_trainer/for_admin/no_passage_available.html', {"error_message": "利用できる問題のバージョンがありません。"})

        elif quiz_type == "eiken_new":
            if not is_valid_eiken_level(eiken_level):
                logger.warning("英検レベルが不正です。(eiken_level=%s)", eiken_level)
                return render(request, "read_trainer/for_admin/generation_failed.html", {
                    "error_message": "英検レベルが不正です。"
                })
            progresses = StudentContextProgress.objects.with_active_student().filter(
                student=student,
                total_count__gt=0
            ).select_related("context")

            sorted_contexts = softmax_permute_contexts_from_progresses(list(progresses))
            if not sorted_contexts:
                logger.warning("利用できる語彙が存在しません。(student: %s)", student)
                return render(request, "read_trainer/for_admin/no_vocab_available.html", {})

            try:
                passage, batch_id = generate_eiken_passage_with_questions(student, eiken_level, sorted_contexts)
            except Exception:
                logger.exception("新規英検問題の生成に失敗しました。")
                return render(request, 'read_trainer/for_admin/generation_failed.html', {
                    "error_message": "新規英検問題の生成に失敗しました。"
                })
                
        elif quiz_type == "eiken_reuse_questions":
            if not is_valid_eiken_level(eiken_level):
                logger.warning("英検レベルが不正です。(eiken_level=%s)", eiken_level)
                return render(request, "read_trainer/for_admin/generation_failed.html", {
                    "error_message": "英検レベルが不正です。"
                })
            passage = passage_access_check(request.user, passage_id, source_type="eiken", expected_student_id=student.id)
            progresses = StudentContextProgress.objects.with_active_student().filter(
                student=student,
                total_count__gt=0
            ).select_related("context")

            sorted_contexts = softmax_permute_contexts_from_progresses(list(progresses))
            if not sorted_contexts:
                logger.warning("利用できる語彙が存在しません。(student: %s)", student)
                return render(request, "read_trainer/for_admin/no_vocab_available.html", {})
            try:
                passage, batch_id = append_questions_to_existing_eiken_passage(student, passage, eiken_level, sorted_contexts)
            except Exception:
                logger.exception("英検再利用問題の生成に失敗しました。")
                return render(request, 'read_trainer/for_admin/generation_failed.html', {
                    "error_message": "英検再利用問題の生成に失敗しました。"
                })
                
        elif quiz_type == "eiken_reuse_all":
            passage = passage_access_check(request.user, passage_id, source_type="eiken", expected_student_id=student.id)
            batch_id = get_latest_batch_for_passage(passage)
            if (batch_id is None) or (not str(batch_id).isdigit()):
                logger.error("バッチIDが存在しません。 (passage_id=%s, batch_id=%s)", passage_id, batch_id)
                return render(request, 'read_trainer/for_admin/no_passage_available.html', {"error_message": "利用できる問題のバージョンが存在しません。"})
        else:
            logger.error("対応していない出題タイプが選択されました。(quiz_type=%s)",quiz_type)
            return render(request, 'read_trainer/for_admin/generation_failed.html', {"error_message": "不明な出題タイプです。"})

        if "eiken" in quiz_type:
            is_eiken = 1
        else:
            is_eiken = 0
        return redirect(
            f"{reverse('read_trainer:admin_solve', args=[passage.id])}?classroom_id={classroom_id}&batch_id={batch_id}&is_eiken={is_eiken}"
        )


class AdminReadingQuizSolveView(View):
    """クイズの回答画面、および結果画面の表示(管理者用)"""
    template_solve = "read_trainer/for_admin/solve.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts_auth:login")
        if not is_admin_or_teacher(request.user):
            ctx = {
                "user_id": request.user.id,
                "user_role": getattr(request.user, "role", None)
            }
            logger.warning(
                "管理者・講師用クイズ回答画面・解答処理に対して、異なるロールのユーザーからアクセスがありました。",
                extra=ctx
            )
            raise PermissionDenied("この機能にアクセスできません。")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        """
        与えられた情報からクイズ画面をレンダリングする
        """
        is_eiken = request.GET.get("is_eiken") == "1"
        if is_eiken:
            source_type = "eiken"
        else:
            source_type = "textbook"
        passage = passage_access_check(request.user, pk, source_type=source_type)
        classroom_id = request.GET.get("classroom_id", "")
        student_id = passage.created_by_id
        student = student_access_check(request.user, student_id)

        try:
            batch_id = get_and_validate_batch_id_from_request(request)
        except ValidationError:
            return render(request, "read_trainer/for_admin/generation_failed.html", {
                "error_message": "バッチIDが不正です。"
            })
        questions = passage.questions.filter(batch_id=batch_id)
        if not questions.exists():
            return render(request, "read_trainer/for_admin/generation_failed.html", {
                "error_message": "指定されたバッチIDの問題が存在しません。"
            })

        context = {
            "passage": passage,
            "student": student,
            "classroom_id": classroom_id,
            "questions": questions,
            "batch_id": batch_id,
            "is_eiken": is_eiken,
        }
        return render(request, self.template_solve, context)

    def post(self, request, pk):
        """
        ユーザーの解答をPOSTとして受けとり、解答画面へ遷移
        """
        student_id_from_post = request.POST.get("student_id")
        if not student_id_from_post:
            logger.warning(
                "POSTにstudent_idが含まれていません。(user.id=%s, passage_id=%s)",
                getattr(request.user, "id", None),
                pk,
            )
            raise PermissionDenied("不正なアクセスです。")
        is_eiken = request.POST.get("is_eiken") == "1"
        if is_eiken:
            source_type = "eiken"
        else:
            source_type = "textbook"
        passage = passage_access_check(request.user, pk, source_type=source_type, expected_student_id=student_id_from_post)
        classroom_id = request.POST.get("classroom_id", "")
        student_id_from_passage = passage.created_by_id
        student = student_access_check(request.user, student_id_from_passage)
        audio_file_names = request.POST.get("audio_file_names", "")

        try:
            batch_id = get_and_validate_batch_id_from_request(request)
        except ValidationError:
            return render(request, "read_trainer/for_admin/scoring_failed.html", {
                "error_message": "バッチIDが不正です。"
            })

        questions = passage.questions.filter(batch_id=batch_id)
        if not questions.exists():
            logger.error("長文に紐づけられた問題が存在しません。(questions: %s, batch_id: %s, passage_id: %s)", questions, batch_id, passage.id)
            return render(request, "read_trainer/for_admin/scoring_failed.html", {
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
                "read_trainer/for_admin/scoring_failed.html",
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
                "read_trainer/for_admin/scoring_failed.html",
                {"error_message": "解答処理中に予期しないエラーが発生しました。"},
            )
        # ✅ 結果をセッションに保存
        request.session["read_quiz_result"] = {
            "passage_id": passage.id,
            "classroom_id": classroom_id,
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
        url = reverse("read_trainer:admin_result")
        return redirect(f"{url}?classroom_id={classroom_id}&target_student_id={student.id}&is_eiken={'1' if is_eiken else '0'}")
    

@require_GET
def admin_result_view(request):
    if not request.user.is_authenticated:
        return redirect("accounts_auth:login")
    if not is_admin_or_teacher(request.user):
        ctx = {
            "user_id": request.user.id,
            "user_role": getattr(request.user, "role", None)
        }
        logger.warning(
            "管理者・講師用クイズ結果表示に対して、異なるロールのユーザーからアクセスがありました。",
            extra=ctx
        )
        raise PermissionDenied("この機能にアクセスできません。")
    data = request.session.pop("read_quiz_result", None)
    if not data:
        classroom_id = request.GET.get("classroom_id")
        target_student_id = request.GET.get("target_student_id")
        is_eiken = request.GET.get("is_eiken") in ("1", "true", "True")
        if classroom_id and target_student_id:
            if is_eiken:
                route = 'read_trainer:eiken_quiz_type_select_with_admin'
            else:
                route = 'read_trainer:quiz_type_select_with_admin'
            return redirect(f"{reverse(route)}?classroom_id={classroom_id}&target_student_id={target_student_id}")
        role = getattr(request.user, "role", None)
        if role == "teacher":
            return redirect("organization_admin:teacher_dashboard")
        elif role in ("classroom_administrator", "organization_administrator"):
            return redirect("organization_admin:classroom_list")
        return redirect("accounts_auth:login")
    is_eiken = data["is_eiken"]
    if is_eiken:
        source_type = "eiken"
    else:
        source_type = "textbook"
    student = student_access_check(request.user, data["student_id"])
    passage = passage_access_check(request.user, data["passage_id"], source_type=source_type, expected_student_id=student.id)
    # 整合性チェック
    student_id_by_passage = passage.created_by_id
    student_id_by_data = student.id
    if str(student_id_by_passage) != str(student_id_by_data):
        logger.warning(
            "生徒の整合性が取れていません。(長文を作成した生徒のID: %s, dataから得られた生徒のID: %s)",
            str(student_id_by_passage), str(student_id_by_data))
        raise PermissionDenied("生徒の整合性が取れていません。")
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
        "classroom_id": data["classroom_id"],
        "results": full_results,
        "is_eiken": is_eiken,
        "audio_file_names": data["audio_file_names"],
    }

    return render(request, "read_trainer/for_admin/result.html", context)
