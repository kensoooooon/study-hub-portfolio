from django.views import View
from django.shortcuts import render, redirect
from django.urls import reverse

from math_trainer.utils import problem_generator, shape_two_columns
from math_trainer.math_process import elementary2
from math_trainer.models import GradeChoices

from django.contrib import messages

from math_trainer.utils.student_access_check import student_access_check
from math_trainer.utils.build_url import build_url
from math_trainer.utils.get_int import get_allowed_int_from_post, get_allowed_int_from_session
from math_trainer.constraints import ALLOWED_PAPER_NUMBERS

import logging

logger = logging.getLogger(__name__)


def redirect_to_elementary2_problem_select(request, *, student_id: str, classroom_id: str, msg: str):
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
    base_url = reverse('math_trainer:elementary2:problem_select')
    return redirect(build_url(base_url, student_id, classroom_id))



class Grade2PrintDispatcherView(View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts_auth:login")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        raw_student_id = request.POST.get("student_id")
        user = request.user
        student = student_access_check(user, raw_student_id)
        student_id = student.id
        classroom_id = request.POST.get("classroom_id")
        paper_number = get_allowed_int_from_post(request, "paper_number", allowed=ALLOWED_PAPER_NUMBERS)
        if paper_number is None:
            error_message = "プリントの枚数を選び直してください。"
            return redirect_to_elementary2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
        request.session["paper_number"] = paper_number
        category = request.POST.get("problem_category")
        if not category:
            error_message = "最低1つの問題カテゴリを選択して下さい。"
            return redirect_to_elementary2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
        if category not in ["clock"]:
            error_message = "想定されていないカテゴリが選択されました。"
            return redirect_to_elementary2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
        if category == "clock":
            problem_types = request.POST.getlist("problem_type")
            if not problem_types:
                error_message = "最低1つの問題タイプを選択してください。"
                return redirect_to_elementary2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
            request.session["problem_types"] = problem_types
            widths_of_time = request.POST.getlist("width_of_time")
            if not widths_of_time:
                error_message = "最低1つの時間幅を選択してください。"
                return redirect_to_elementary2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
            request.session["widths_of_time"] = widths_of_time
            base_url = reverse('math_trainer:elementary2:clock_print')
            url = build_url(base_url, student_id, classroom_id)
            return redirect(url)

        error_message = "想定していない動作です。管理者にお知らせ下さい。"
        return redirect_to_elementary2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)


class ClockPrintView(View):
    template_name = "math_trainer/elementary2/clock/for_print.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts_auth:login")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        """クイズ画面の表示"""
        classroom_id = request.GET.get("classroom_id")
        user = request.user
        raw_student_id = request.GET.get("student_id")
        student = student_access_check(user, raw_student_id)
        student_id = student.id
        
        problem_name = "時計"
        problem_grade = GradeChoices.ELEMENTARY_2
        
        problem_types = request.session.get("problem_types", None)
        if problem_types is None:
            error_message = "問題タイプを選び直してください。"
            return redirect_to_elementary2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
        widths_of_time = request.session.get("widths_of_time", None)
        if widths_of_time is None:
            error_message = "時間幅を選び直してください。"
            return redirect_to_elementary2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
        
        paper_number = get_allowed_int_from_session(request, "paper_number", allowed=ALLOWED_PAPER_NUMBERS)
        if paper_number is None:
            error_message = "プリントの枚数を選び直してください。"
            return redirect_to_elementary2_problem_select(request, student_id=student_id, classroom_id=classroom_id, msg=error_message)
        
        PROBLEM_NUMBER = 6

        generator_instance = elementary2.clock_generator.ClockProblemGenerator(
            problem_types=problem_types, widths_of_time=widths_of_time
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
