from django.shortcuts import render, get_object_or_404, redirect
from django.views import View

from listening_trainer.models import ListeningPassage, StudentListeningPassageProgress
from vocab_trainer.models import WordMeaningContext, Student
from vocab_trainer.models import StudentContextProgress


from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse

from listening_trainer.utils.quiz_generation import (
    generate_and_save_passage_with_questions,
    append_questions_to_existing_passage,
    get_latest_batch_for_passage,
    generate_eiken_passage_with_questions,
    append_questions_to_existing_eiken_passage,
)
from listening_trainer.utils.quiz_scoring import process_listening_answers
from listening_trainer.utils.quiz_selection import select_passages_for_student

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# OIDC認証
from auth.oidc_verify import require_oidc_token

from django.views.decorators.http import require_GET

from django.utils import timezone

from listening_trainer.services import softmax_permute_contexts_from_progresses


from django.utils.decorators import method_decorator

from django.core.exceptions import PermissionDenied

import logging

logger = logging.getLogger(__name__)

def is_student(user):
    return user.role == "student"

@login_required
@user_passes_test(is_student)
def quiz_type_select_for_student(request):
    """POST,Getの両方に対応したクイズタイプ選択画面"""
    student = request.user.get_role_object()
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


@login_required
@user_passes_test(is_student)
def eiken_quiz_type_select_for_student(request):
    """生徒用のクイズ選択を表示"""
    student = request.user.get_role_object()
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


@method_decorator([login_required, user_passes_test(is_student)], name="dispatch")
class StudentListeningQuizDispatcherView(View):
    def post(self, request):
        quiz_type = request.POST.get("quiz_type")
        student = request.user.get_role_object()
        eiken_level = request.POST.get("eiken_level")

        if quiz_type is None:
            logger.error("クイズタイプが指定されていません。")
            return render(request, 'listening_trainer/for_student/generation_failed.html', {"error_message": "クイズタイプが指定されていません。"})
        
        if quiz_type == "new":
            progresses = StudentContextProgress.objects.filter(
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
            passage = get_object_or_404(ListeningPassage, id=passage_id, created_by=student, source_type="textbook")
            progresses = StudentContextProgress.objects.filter(
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
            passage = get_object_or_404(ListeningPassage, id=passage_id, created_by=student, source_type="textbook")

            batch_id = get_latest_batch_for_passage(passage)
            if (batch_id is None) or (not str(batch_id).isdigit()):
                logger.error("batch_idが存在しません。(passage_id: %s, batch_id: %s)",
                            passage_id, batch_id)
                return render(request, 'listening_trainer/for_student/no_passage_available.html', {"error_message": "利用できる問題バージョンが存在しません。"})

    
        elif quiz_type == "eiken_new":
            progresses = StudentContextProgress.objects.filter(
                student=student,
                total_count__gt=0
            ).select_related("context")

            sorted_contexts = softmax_permute_contexts_from_progresses(list(progresses))
            if not sorted_contexts:
                logger.warning("利用できる語彙が存在しません。(student: %s)", student)
                return render(request, "listening_trainer/for_student/no_vocab_available.html")
            try:
                passage, batch_id = generate_eiken_passage_with_questions(student, eiken_level, sorted_contexts)
            except Exception:
                logger.exception("新規英検用リスニング問題の再生成に失敗しました。")
                return render(request, 'listening_trainer/for_student/generation_failed.html', {
                    "error_message": "新規英検用リスニング問題の生成に失敗しました。"
                })

        elif quiz_type == "eiken_reuse_questions":
            passage_id = request.POST.get("passage_id")            
            passage = get_object_or_404(ListeningPassage, id=passage_id, created_by=student, source_type="eiken")
            
            progresses = StudentContextProgress.objects.filter(
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
            passage = get_object_or_404(ListeningPassage, id=passage_id, created_by=student, source_type="eiken")

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


@method_decorator([login_required, user_passes_test(is_student)], name="dispatch")
class StudentListeningQuizSolveView(View):
    """クイズの回答画面、および結果画面の表示"""
    template_solve = "listening_trainer/for_student/solve.html"

    def get(self, request, pk):
        passage = get_object_or_404(ListeningPassage, pk=pk)
        batch_id = request.GET.get("batch_id")
        is_eiken = request.GET.get("is_eiken") == "1"
        
        # 自分以外の生徒の長文にはアクセス不可
        student = request.user.get_role_object()
        if str(passage.created_by.id) != str(student.id):
            logger.warning(
                "不正アクセスの可能性(アクセスした生徒ID: %s, 長文を作成した生徒ID: %s)",
                student.id,
                passage.created_by.id,
            )
            raise PermissionDenied("この長文にはアクセスできません。")
        
        if batch_id:
            questions = passage.questions.filter(batch_id=batch_id)
        else:
            questions = passage.questions.all()

        context = {
            "passage": passage,
            "student": passage.created_by,
            "questions": questions,
            "batch_id": batch_id,
            "is_eiken": is_eiken
        }
        return render(request, self.template_solve, context)

    def post(self, request, pk):
        passage = get_object_or_404(ListeningPassage, pk=pk)
        student = request.user.get_role_object()
        is_eiken = request.POST.get("is_eiken") == "1"
        audio_file_names = request.POST.get("audio_file_names", "")

        # 生徒の不整合
        create_student = passage.created_by
        if str(student.id) != str(create_student.id):
            logger.warning(
                "不正アクセスの可能性(アクセスした生徒のID: %s, 長文を作成した生徒のID: %s)",
                student.id, create_student.id
            )
            raise PermissionDenied("この長文にはアクセスできません。")

        # 必須チェック
        batch_id_raw = request.POST.get("batch_id")

        if not batch_id_raw:
            logger.error("バッチIDが送信されていません。(batch_id: %s)", batch_id_raw)
            return render(request, "listening_trainer/for_student/scoring_failed.html", {
                "error_message": "バッチIDが不正です。"
            })

        try:
            batch_id = int(batch_id_raw)
        except (ValueError, TypeError):
            logger.exception(
                "バッチIDの値もしくは型のエラー(batch_id: %s, type(batch_id): %s)",
                batch_id_raw,
                type(batch_id_raw),
            )
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

        # ✅ 結果をセッションに保存
        request.session["listening_quiz_result"] = {
            "passage_id": passage.id,
            "student_id": str(student.id),
            "is_eiken": is_eiken,
            "audio_file_names": audio_file_names,
            "batch_id": int(batch_id),
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
        url = reverse("listening_trainer:student_result")
        return redirect(f"{url}?is_eiken={'1' if is_eiken else '0'}")


@login_required
@user_passes_test(is_student)
@require_GET
def student_result_view(request):
    data = request.session.pop("listening_quiz_result", None)
    if not data:
        is_eiken = request.GET.get("is_eiken") in ("1", "true", "True")
        if is_eiken:
            return redirect("listening_trainer:eiken_quiz_type_select_for_student")
        else:
            return redirect("listening_trainer:quiz_type_select_for_student")
    passage = get_object_or_404(ListeningPassage, pk=data["passage_id"])
    student = get_object_or_404(Student, pk=data["student_id"])
    # dataから得られた生徒とログインしている生徒が一致しているか
    current_student = request.user.get_role_object()
    if str(student.id) != str(current_student.id):
        logger.warning(
            "結果画面への不正アクセスの可能性 (ログイン生徒ID: %s, 結果データの生徒ID: %s)",
            current_student.id,
            student.id,
        )
        raise PermissionDenied("この結果にはアクセスできません。")
    # 長文を作成した生徒とdataから得られた生徒の整合性
    student_id_by_passage = passage.created_by.id
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
        "results": full_results,
        "is_eiken": data["is_eiken"],
        "audio_file_names": data["audio_file_names"],
    }

    return render(request, "listening_trainer/for_student/result.html", context)
