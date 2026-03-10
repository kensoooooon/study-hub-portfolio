from django.views import View
from django.shortcuts import render, redirect
from django.urls import reverse

from math_trainer.utils import problem_generator, shape_two_columns

from math_trainer.models import GradeChoices

from math_trainer.math_process import junior_high1

from django.contrib import messages

from django.contrib.auth.mixins import LoginRequiredMixin

from math_trainer.utils.student_access_check import student_access_check
from math_trainer.utils.build_url import build_url
from math_trainer.utils.get_int import get_allowed_int_from_post, get_allowed_int_from_session
from math_trainer.constraints import ALLOWED_PAPER_NUMBERS


def redirect_to_junior_high1_problem_select(request, *, student_id: str, classroom_id: str, msg: str):
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
    base_url = reverse('math_trainer:junior_high1:problem_select')
    return redirect(build_url(base_url, student_id, classroom_id))


class JuniorHigh1PrintDispatcherView(LoginRequiredMixin, View):
    def post(self, request):
        user = request.user
        raw_student_id = request.POST.get("student_id", "")
        student = student_access_check(user, raw_student_id)
        student_id = student.id
        classroom_id = request.POST.get("classroom_id", "")
        paper_number = get_allowed_int_from_post(request, "paper_number", allowed=ALLOWED_PAPER_NUMBERS)
        if paper_number is None:
            error_message = "プリントの枚数を選び直してください。"
            return redirect_to_junior_high1_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
        request.session["paper_number"] = paper_number
        
        category = request.POST.get("problem_category")
        if category == "specific_linear_equation":
            problem_types = request.POST.getlist("problem_type")
            if not problem_types:
                error_message = "最低1つの問題タイプを選択してください。"
                return redirect_to_junior_high1_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
            request.session["problem_types"] = problem_types
            
            numbers_to_use = request.POST.getlist("number_to_use")
            if not numbers_to_use:
                error_message = "最低1つの使用する数のタイプを選択してください。"
                return redirect_to_junior_high1_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
            request.session["numbers_to_use"] = numbers_to_use

            base_url = reverse('math_trainer:junior_high1:specific_linear_equation_print')
            url = build_url(base_url, student_id, classroom_id)
            return redirect(url)
        else:
            return render(request, "math_trainer/common/no_category.html")


class SpecificLinearEquationPrintView(LoginRequiredMixin, View):
    template_name = "math_trainer/junior_high1/specific_linear_equation/for_print.html"

    def get(self, request):
        """クイズ画面の表示"""
        classroom_id = request.GET.get("classroom_id")
        user = request.user
        raw_student_id = request.GET.get("student_id")
        student = student_access_check(user, raw_student_id)
        student_id = student.id
        problem_name = "特定の形を持つ1次方程式"
        problem_grade = GradeChoices.JUNIOR_HIGH_1
        
        problem_types = request.session.get("problem_types", None)
        if problem_types is None:
            error_message = "最低1つの問題タイプを選択してください。"
            return redirect_to_junior_high1_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)

        numbers_to_use = request.session.get("numbers_to_use", None)
        if numbers_to_use is None:
            error_message = "最低1つの使用する数のタイプを選択してください。"
            return redirect_to_junior_high1_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)

        paper_number = get_allowed_int_from_session(request, "paper_number", allowed=ALLOWED_PAPER_NUMBERS)
        if paper_number is None:
            error_message = "プリントの枚数を選び直してください。"
            return redirect_to_junior_high1_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
        
        PROBLEM_NUMBER = 10

        generator_instance = junior_high1.specific_linear_equation_generator.SpecificLinearEquationGenerator(
            problem_types=problem_types, numbers_to_use=numbers_to_use
        )
        # [紙][(左,右), (左,右), ...] を作る
        pages = []
        for _ in range(paper_number):
            problems, problem_session = problem_generator.problem_generator(
                student=student, problem_name=problem_name,
                problem_grade=problem_grade, mode="print",
                num_of_problem=PROBLEM_NUMBER, generator_instance=generator_instance
            )
            session_id = problem_session.id
            pairs = shape_two_columns.group_into_tuples(problems)  # [(p0,p1),(p2,p3),...]
            pages.append({"session_id": str(session_id), "pairs": pairs})

        context = {
            "pages": pages,              # 問題ページ用(セッションIDつき)
            "paper_number": paper_number, # 解答ページの見出し等に流用可
            "classroom_id": classroom_id,
            "student_id": student_id,
        }
        return render(request, self.template_name, context)
