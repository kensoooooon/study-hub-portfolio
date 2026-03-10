from django.views.generic import TemplateView

from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET

from math_trainer.utils import problem_generator, shape_two_columns

from math_trainer.models import GradeChoices, ProblemSession, ProblemInstance

from math_trainer.math_process import junior_high2

from django.contrib import messages


from math_trainer.math_process.junior_high2.simultaneous_equations_generator import InvalidSettingsError

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required

from math_trainer.utils.student_access_check import student_access_check
from math_trainer.utils.build_url import build_url
from math_trainer.utils.session_access_check import session_access_check

def redirect_to_junior_high2_problem_select(request, *, student_id: str, classroom_id: str, msg: str):
    """何かしらの不備があった場合に、問題選択に飛ばす関数

    Args:
        request: リクエスト
        student_id (str): 対象となる生徒ID
        classroom_id (str): 対象となる教室ID
        msg (str): エラー・メッセージとしてブラウザに表示したい文言

    Returns:
        redirect: ページ遷移用のオブジェクト
    """
    messages.error(request, msg)
    base_url = reverse('math_trainer:junior_high2:problem_select')
    return redirect(build_url(base_url, student_id, classroom_id))


class JuniorHigh2DisplayDispatcherView(LoginRequiredMixin, View):
    def post(self, request):
        user = request.user
        raw_student_id = request.POST.get("student_id", "")
        student = student_access_check(user, raw_student_id)
        student_id = student.id
        classroom_id = request.POST.get("classroom_id", "")

        category = request.POST.get("problem_category")
        # 適宜問題タイプを追加する
        if category == "simultaneous_equations":
            used_coefficients = request.POST.getlist("used_coefficient")
            if not used_coefficients:
                error_message = "最低1つの使用する係数を選択してください。"
                return redirect_to_junior_high2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
            request.session["used_coefficients"] = used_coefficients
            equation_types = request.POST.getlist("equation_type")
            if not equation_types:
                error_message = "最低1つの問題タイプを選択してください。"
                return redirect_to_junior_high2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
            request.session["equation_types"] = equation_types
            answer_types = request.POST.getlist("answer_type")
            if not answer_types:
                error_message = "最低1つの問題タイプを選択してください。"
                return redirect_to_junior_high2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
            request.session["answer_types"] = answer_types
            base_url = reverse('math_trainer:junior_high2:simultaneous_equations_display')
            url = build_url(base_url, student_id, classroom_id)
            return redirect(url)
        else:
            return render(request, "math_trainer/common/no_category.html")


class SimultaneousEquationsDisplayView(LoginRequiredMixin, TemplateView):
    """
    連立方程式を解く問題の作成と採点
    """
    template_name = "math_trainer/junior_high2/simultaneous_equations/for_display.html"
    
    def get(self, request):
        """
        クイズ画面の表示
        """
        classroom_id = request.GET.get("classroom_id")
        user = request.user
        raw_student_id = request.GET.get("student_id")
        student = student_access_check(user, raw_student_id)
        student_id = student.id
        problem_name = "連立方程式の計算"
        problem_grade = GradeChoices.JUNIOR_HIGH_2
        equation_types = request.session.get("equation_types", None)
        if equation_types is None:
            error_message = "最低1つの問題タイプを選択してください。"
            return redirect_to_junior_high2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
        used_coefficients = request.session.get("used_coefficients", None)
        if used_coefficients is None:
            error_message = "最低1つの使用する係数を選択してください。"
            return redirect_to_junior_high2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
        answer_types = request.session.get("answer_types", None)
        if not answer_types:
            error_message = "最低1つの問題タイプを選択してください。"
            return redirect_to_junior_high2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
        try:
            generator_instance = junior_high2.simultaneous_equations_generator.SimultaneousEquationsGenerator(
                equation_types=equation_types, used_coefficients=used_coefficients,
                answer_types=answer_types
            )
        except InvalidSettingsError as e:
            messages.error(request, "問題の条件に不正な値が含まれています。選択肢を見直してください。")
            base_url = reverse('math_trainer:junior_high2:problem_select')
            url = build_url(base_url, student_id, classroom_id)
            return redirect(url)
        problems, problem_session = problem_generator.problem_generator(
            student=student, problem_name=problem_name,
            problem_grade=problem_grade, mode="display",
            num_of_problem=10, generator_instance=generator_instance
        )
        math_problem_tuples = shape_two_columns.group_into_tuples(problems)
        problem_session_id = problem_session.id
        context = {
            "student_id": student_id,
            "classroom_id": classroom_id,
            "math_problem_tuples": math_problem_tuples,
            "problem_session_id": problem_session_id
        }
        return render(request, self.template_name, context)

    def post(self, request):
        """
        返ってきた解答を採点し、結果表示にリダイレクトする
        """
        classroom_id = request.GET.get("classroom_id")
        user = request.user
        raw_student_id = request.GET.get("student_id")
        student = student_access_check(user, raw_student_id)
        student_id = student.id
        raw_session_id = request.POST.get("problem_session_id")

        session = session_access_check(user, raw_session_id, mode="display")
        # このセッションに属する問題のみを採点対象に
        instances = ProblemInstance.objects.filter(session=session).order_by('id')

        results = []
        correct_count = 0
        total = 0

        for inst in instances:
            total += 1
            key = f"q_{inst.id}"  # ← name="q_<instance_id>" と一致
            raw = request.POST.get(key)
            if raw is None or not raw.isdigit():
                # 不正 or 未回答：ここでは不正扱い
                selected_idx = None
                is_correct = False
                selected_text = None
            else:
                selected_idx = int(raw)
                # 選択肢範囲チェック
                if selected_idx < 0 or selected_idx >= len(inst.choice_texts):
                    selected_idx = None
                    is_correct = False
                    selected_text = None
                else:
                    selected_text = inst.choice_texts[selected_idx]
                    is_correct = (selected_text == inst.answer_text)

            if is_correct:
                correct_count += 1

            results.append({
                "instance": inst,
                "selected_index": selected_idx,
                "selected_text": selected_text,
                "is_correct": is_correct,
            })

        request.session["math_quiz_result"] = {
            "problem_session_id": str(session.id),
            "classroom_id": classroom_id,
            "student_id": str(student_id),
            "summary": {"correct": correct_count, "total": total},
            "items": [
                {
                    "instance_id": r["instance"].id,
                    "selected_index": r["selected_index"],
                    "is_correct": r["is_correct"],
                } for r in results
            ],
        }

        base_url = reverse("math_trainer:junior_high2:simultaneous_equations_result")
        url = build_url(base_url, student_id, classroom_id)
        return redirect(url)
    

@login_required
@require_GET
def simultaneous_equations_result_view(request):
    data = request.session.pop("math_quiz_result", None)
    if not data:
        classroom_id = request.GET.get("classroom_id")
        user = request.user
        raw_student_id = request.GET.get("student_id")
        student = student_access_check(user, raw_student_id)
        student_id = student.id
        base_url = reverse('math_trainer:index')
        url = build_url(base_url, student_id, classroom_id)
        return redirect(url)

    raw_session_id = data["problem_session_id"]
    user = request.user
    session = session_access_check(user, raw_session_id, mode="display")
    instances = ProblemInstance.objects.filter(session=session)

    # （任意）表示順の復元：display_order を持っていればそれで、無ければ id
    if hasattr(ProblemInstance, "display_order"):
        instances = instances.order_by("display_order")
    else:
        instances = instances.order_by("id")

    result_map = {item["instance_id"]: item for item in data["items"]}
    full_results = []
    for inst in instances:
        item = result_map.get(inst.id, {})
        sel_idx = item.get("selected_index")
        full_results.append({
            "instance_id": inst.id,
            "problem_text": inst.question_text,
            "options": list(enumerate(inst.choice_texts)) if inst.choice_texts else [],
            "selected_index": sel_idx,
            "selected_text": (inst.choice_texts[sel_idx] if sel_idx is not None and 0 <= sel_idx < len(inst.choice_texts) else None),
            "is_correct": item.get("is_correct", False),
            "answer_text": inst.answer_text,
        })

    context = {
        "session": session,
        "results": full_results,
        "summary": data["summary"],
        "classroom_id": data["classroom_id"],
        "student_id": data["student_id"],
    }
    return render(request, "math_trainer/junior_high2/simultaneous_equations/result.html", context)
