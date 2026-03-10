from django.views import View
from django.shortcuts import render, redirect
from django.urls import reverse

from math_trainer.utils import problem_generator, shape_two_columns

from math_trainer.models import GradeChoices

from math_trainer.math_process import junior_high2

from django.contrib import messages

from math_trainer.math_process.junior_high2.simultaneous_equations_generator import InvalidSettingsError

from django.contrib.auth.mixins import LoginRequiredMixin

from math_trainer.utils.student_access_check import student_access_check
from math_trainer.utils.build_url import build_url
from math_trainer.utils.get_int import get_allowed_int_from_post, get_allowed_int_from_session
from math_trainer.constraints import ALLOWED_PAPER_NUMBERS


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


class JuniorHigh2PrintDispatcherView(LoginRequiredMixin, View):
    def post(self, request):
        user = request.user
        raw_student_id = request.POST.get("student_id", "")
        student = student_access_check(user, raw_student_id)
        student_id = student.id
        classroom_id = request.POST.get("classroom_id", "")
        
        paper_number = get_allowed_int_from_post(request, "paper_number", allowed=ALLOWED_PAPER_NUMBERS)
        if paper_number is None:
            error_message = "プリントの枚数を選択してください。"
            return redirect_to_junior_high2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
        request.session["paper_number"] = paper_number

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
                error_message = "最低1つの解のタイプを選択してください。"
                return redirect_to_junior_high2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
            request.session["answer_types"] = answer_types
            
            base_url = reverse('math_trainer:junior_high2:simultaneous_equations_print')
            url = build_url(base_url, student_id, classroom_id)
            return redirect(url)
        else:
            return render(request, "math_trainer/common/no_category.html", {})


class SimultaneousEquationsPrintView(LoginRequiredMixin, View):
    template_name = "math_trainer/junior_high2/simultaneous_equations/for_print.html"

    def get(self, request):
        """クイズ画面の表示"""
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
        if answer_types is None:
            error_message = "最低1つの解のタイプを選択してください。"
            return redirect_to_junior_high2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
        
        generator_instance = junior_high2.simultaneous_equations_generator.SimultaneousEquationsGenerator(
            equation_types=equation_types, used_coefficients=used_coefficients,
            answer_types=answer_types
        )
        
        paper_number = get_allowed_int_from_session(request, "paper_number", allowed=ALLOWED_PAPER_NUMBERS)
        if paper_number is None:
            error_message = "プリントの枚数を選択してください。"
            return redirect_to_junior_high2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)

        
        PROBLEM_NUMBER = 10
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
