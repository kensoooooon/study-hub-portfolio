from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from math_trainer.constraints import ALLOWED_PAPER_NUMBERS

# junior_high2 の urls は "from math_trainer.views import junior_high2" 形式
# ただし student_access_check は各 view モジュール内で import されているので、
# patch 対象は view モジュールごとに分ける必要がある。
JH2_SELECT = "math_trainer.views.junior_high2.problem_select_views"
JH2_PRINT = "math_trainer.views.junior_high2.print_views"
JH2_DISPLAY = "math_trainer.views.junior_high2.display_views"


class JuniorHigh2AllViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u1", password="pass")
        self.client.force_login(self.user)

        self.student = SimpleNamespace(id=123)
        self.student_id = str(self.student.id)
        self.classroom_id = "456"

        # URLs
        self.url_problem_select = reverse("math_trainer:junior_high2:problem_select")

        self.url_dispatcher_print = reverse("math_trainer:junior_high2:dispatcher_print")
        self.url_simul_print = reverse("math_trainer:junior_high2:simultaneous_equations_print")

        self.url_dispatcher_display = reverse("math_trainer:junior_high2:dispatcher_display")
        self.url_simul_display = reverse("math_trainer:junior_high2:simultaneous_equations_display")
        self.url_simul_result = reverse("math_trainer:junior_high2:simultaneous_equations_result")

        self.allowed_paper = min(ALLOWED_PAPER_NUMBERS)

    # -------------------------
    # problem_select
    # -------------------------
    @patch(f"{JH2_SELECT}.student_access_check")
    def test_problem_select_get_requires_login(self, mock_access):
        self.client.logout()
        res = self.client.get(
            self.url_problem_select,
            data={"student_id": self.student_id, "classroom_id": self.classroom_id},
        )
        self.assertEqual(res.status_code, 302)
        mock_access.assert_not_called()

    @patch(f"{JH2_SELECT}.student_access_check")
    def test_problem_select_get_success(self, mock_access):
        mock_access.return_value = self.student
        res = self.client.get(
            self.url_problem_select,
            data={"student_id": self.student_id, "classroom_id": self.classroom_id},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["student_id"], self.student.id)

    # -------------------------
    # print dispatcher
    # -------------------------
    def _post_print_dispatcher(self, **overrides):
        data = {
            "student_id": self.student_id,
            "classroom_id": self.classroom_id,
            "paper_number": str(self.allowed_paper),
            "problem_category": "simultaneous_equations",
            "used_coefficient": ["2"],
            "equation_type": ["standard"],
            "answer_type": ["integer"],
        }
        data.update(overrides)
        return self.client.post(self.url_dispatcher_print, data=data)

    @patch(f"{JH2_PRINT}.student_access_check")
    def test_print_dispatcher_requires_login(self, mock_access):
        self.client.logout()
        res = self._post_print_dispatcher()
        self.assertEqual(res.status_code, 302)
        mock_access.assert_not_called()

    @patch(f"{JH2_PRINT}.student_access_check")
    def test_print_dispatcher_invalid_paper_number_redirects(self, mock_access):
        mock_access.return_value = self.student
        res = self._post_print_dispatcher(paper_number="9999")

        # 仕様：不備は problem_select へ戻す
        expected = f"{self.url_problem_select}?student_id={self.student_id}&classroom_id={self.classroom_id}"
        self.assertRedirects(res, expected, fetch_redirect_response=False)

    @patch(f"{JH2_PRINT}.student_access_check")
    def test_print_dispatcher_missing_used_coefficients_redirects(self, mock_access):
        mock_access.return_value = self.student
        res = self._post_print_dispatcher(used_coefficient=[])

        expected = f"{self.url_problem_select}?student_id={self.student_id}&classroom_id={self.classroom_id}"
        self.assertRedirects(res, expected, fetch_redirect_response=False)

    @patch(f"{JH2_PRINT}.student_access_check")
    def test_print_dispatcher_missing_equation_types_redirects(self, mock_access):
        mock_access.return_value = self.student
        res = self._post_print_dispatcher(equation_type=[])

        expected = f"{self.url_problem_select}?student_id={self.student_id}&classroom_id={self.classroom_id}"
        self.assertRedirects(res, expected, fetch_redirect_response=False)

    @patch(f"{JH2_PRINT}.student_access_check")
    def test_print_dispatcher_missing_answer_types_redirects(self, mock_access):
        mock_access.return_value = self.student
        res = self._post_print_dispatcher(answer_type=[])

        expected = f"{self.url_problem_select}?student_id={self.student_id}&classroom_id={self.classroom_id}"
        self.assertRedirects(res, expected, fetch_redirect_response=False)

    @patch(f"{JH2_PRINT}.student_access_check")
    def test_print_dispatcher_success_sets_session_and_redirects(self, mock_access):
        mock_access.return_value = self.student
        res = self._post_print_dispatcher()

        expected = f"{self.url_simul_print}?student_id={self.student_id}&classroom_id={self.classroom_id}"
        self.assertRedirects(res, expected, fetch_redirect_response=False)

        s = self.client.session
        self.assertEqual(s.get("paper_number"), self.allowed_paper)
        self.assertEqual(s.get("used_coefficients"), ["2"])
        self.assertEqual(s.get("equation_types"), ["standard"])
        self.assertEqual(s.get("answer_types"), ["integer"])

    # -------------------------
    # print view
    # -------------------------
    @patch(f"{JH2_PRINT}.student_access_check")
    def test_simul_print_missing_session_redirects(self, mock_access):
        mock_access.return_value = self.student

        s = self.client.session
        for k in ("paper_number", "used_coefficients", "equation_types", "answer_types"):
            s.pop(k, None)
        s.save()

        res = self.client.get(
            self.url_simul_print,
            data={"student_id": self.student_id, "classroom_id": self.classroom_id},
        )

        expected = f"{self.url_problem_select}?student_id={self.student_id}&classroom_id={self.classroom_id}"
        self.assertRedirects(res, expected, fetch_redirect_response=False)

    @patch(f"{JH2_PRINT}.shape_two_columns.group_into_tuples")
    @patch(f"{JH2_PRINT}.problem_generator.problem_generator")
    @patch(f"{JH2_PRINT}.junior_high2.simultaneous_equations_generator.SimultaneousEquationsGenerator")
    @patch(f"{JH2_PRINT}.student_access_check")
    def test_simul_print_success_renders_pages(
        self, mock_access, mock_generator_cls, mock_problem_generator, mock_group
    ):
        mock_access.return_value = self.student
        mock_generator_cls.return_value = SimpleNamespace()

        # session 前提
        s = self.client.session
        s["paper_number"] = self.allowed_paper
        s["used_coefficients"] = ["2"]
        s["equation_types"] = ["standard"]
        s["answer_types"] = ["integer"]
        s.save()

        fake_problems = [SimpleNamespace(id=i) for i in range(10)]
        fake_session = SimpleNamespace(id=999)
        mock_problem_generator.return_value = (fake_problems, fake_session)
        mock_group.return_value = [("p0", "p1")]

        res = self.client.get(
            self.url_simul_print,
            data={"student_id": self.student_id, "classroom_id": self.classroom_id},
        )
        self.assertEqual(res.status_code, 200)

        pages = res.context["pages"]
        self.assertEqual(len(pages), self.allowed_paper)
        self.assertEqual(res.context["paper_number"], self.allowed_paper)

        self.assertEqual(mock_problem_generator.call_count, self.allowed_paper)

    # -------------------------
    # display dispatcher
    # -------------------------
    def _post_display_dispatcher(self, **overrides):
        data = {
            "student_id": self.student_id,
            "classroom_id": self.classroom_id,
            "problem_category": "simultaneous_equations",
            "used_coefficient": ["2"],
            "equation_type": ["standard"],
            "answer_type": ["integer"],
        }
        data.update(overrides)
        return self.client.post(self.url_dispatcher_display, data=data)

    @patch(f"{JH2_DISPLAY}.student_access_check")
    def test_display_dispatcher_requires_login(self, mock_access):
        self.client.logout()
        res = self._post_display_dispatcher()
        self.assertEqual(res.status_code, 302)
        mock_access.assert_not_called()

    @patch(f"{JH2_DISPLAY}.student_access_check")
    def test_display_dispatcher_missing_used_coefficients_redirects(self, mock_access):
        mock_access.return_value = self.student
        res = self._post_display_dispatcher(used_coefficient=[])

        expected = f"{self.url_problem_select}?student_id={self.student_id}&classroom_id={self.classroom_id}"
        self.assertRedirects(res, expected, fetch_redirect_response=False)

    @patch(f"{JH2_DISPLAY}.student_access_check")
    def test_display_dispatcher_missing_equation_types_redirects(self, mock_access):
        mock_access.return_value = self.student
        res = self._post_display_dispatcher(equation_type=[])

        expected = f"{self.url_problem_select}?student_id={self.student_id}&classroom_id={self.classroom_id}"
        self.assertRedirects(res, expected, fetch_redirect_response=False)

    @patch(f"{JH2_DISPLAY}.student_access_check")
    def test_display_dispatcher_missing_answer_types_redirects(self, mock_access):
        mock_access.return_value = self.student
        res = self._post_display_dispatcher(answer_type=[])

        expected = f"{self.url_problem_select}?student_id={self.student_id}&classroom_id={self.classroom_id}"
        self.assertRedirects(res, expected, fetch_redirect_response=False)

    @patch(f"{JH2_DISPLAY}.student_access_check")
    def test_display_dispatcher_success_sets_session_and_redirects(self, mock_access):
        mock_access.return_value = self.student
        res = self._post_display_dispatcher()

        expected = f"{self.url_simul_display}?student_id={self.student_id}&classroom_id={self.classroom_id}"
        self.assertRedirects(res, expected, fetch_redirect_response=False)

        s = self.client.session
        self.assertEqual(s.get("used_coefficients"), ["2"])
        self.assertEqual(s.get("equation_types"), ["standard"])
        self.assertEqual(s.get("answer_types"), ["integer"])

    # -------------------------
    # display view GET + POST + result
    # -------------------------
    @patch(f"{JH2_DISPLAY}.shape_two_columns.group_into_tuples")
    @patch(f"{JH2_DISPLAY}.problem_generator.problem_generator")
    @patch(f"{JH2_DISPLAY}.junior_high2.simultaneous_equations_generator.SimultaneousEquationsGenerator")
    @patch(f"{JH2_DISPLAY}.student_access_check")
    def test_simul_display_get_success_renders(
        self, mock_access, mock_generator_cls, mock_problem_generator, mock_group
    ):
        mock_access.return_value = self.student
        mock_generator_cls.return_value = SimpleNamespace()

        s = self.client.session
        s["used_coefficients"] = ["2"]
        s["equation_types"] = ["standard"]
        s["answer_types"] = ["integer"]
        s.save()

        fake_problems = [SimpleNamespace(id=i) for i in range(10)]
        fake_session = SimpleNamespace(id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        mock_problem_generator.return_value = (fake_problems, fake_session)
        mock_group.return_value = [("p0", "p1")]

        res = self.client.get(
            self.url_simul_display,
            data={"student_id": self.student_id, "classroom_id": self.classroom_id},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("problem_session_id", res.context)

    @patch(f"{JH2_DISPLAY}.ProblemInstance")
    @patch(f"{JH2_DISPLAY}.session_access_check")
    @patch(f"{JH2_DISPLAY}.student_access_check")
    def test_simul_display_post_sets_math_quiz_result_and_redirects(
        self, mock_access, mock_session_access, mock_problem_instance_model
    ):
        mock_access.return_value = self.student
        fake_session = SimpleNamespace(id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        mock_session_access.return_value = fake_session

        inst1 = SimpleNamespace(id=1, choice_texts=["A", "B"], answer_text="A", question_text="Q1", metadata={})
        inst2 = SimpleNamespace(id=2, choice_texts=["C", "D"], answer_text="D", question_text="Q2", metadata={})

        qs = SimpleNamespace(order_by=lambda *args, **kwargs: [inst1, inst2])
        mock_problem_instance_model.objects.filter.return_value = qs

        post_data = {"problem_session_id": str(fake_session.id), "q_1": "0", "q_2": "1"}  # 両方正解
        res = self.client.post(
            self.url_simul_display + f"?student_id={self.student_id}&classroom_id={self.classroom_id}",
            data=post_data,
        )

        expected = f"{self.url_simul_result}?student_id={self.student_id}&classroom_id={self.classroom_id}"
        self.assertRedirects(res, expected, fetch_redirect_response=False)

        s = self.client.session
        data = s.get("math_quiz_result")
        self.assertIsNotNone(data)
        self.assertEqual(data["summary"]["correct"], 2)
        self.assertEqual(data["summary"]["total"], 2)

    @patch(f"{JH2_DISPLAY}.student_access_check")
    def test_simul_result_view_no_data_redirects_to_index(self, mock_access):
        """
        result：sessionに math_quiz_result が無い場合、index に戻す
        """
        mock_access.return_value = self.student

        s = self.client.session
        s.pop("math_quiz_result", None)
        s.save()

        res = self.client.get(
            self.url_simul_result,
            data={"student_id": self.student_id, "classroom_id": self.classroom_id},
        )
        self.assertEqual(res.status_code, 302)
        # ここは index へ戻る仕様だが、index 側の build_url 実装差分に影響されやすいので、最低限の検証に留める
        self.assertIn(reverse("math_trainer:index"), res["Location"])

    # -------------------------
    # display dispatcher: カテゴリ検証
    # -------------------------
    @patch(f"{JH2_DISPLAY}.student_access_check")
    def test_display_dispatcher_missing_category_redirects(self, mock_access):
        """problem_category 未送信は problem_select へリダイレクト"""
        mock_access.return_value = self.student
        res = self._post_display_dispatcher(problem_category="")

        expected = f"{self.url_problem_select}?student_id={self.student_id}&classroom_id={self.classroom_id}"
        self.assertRedirects(res, expected, fetch_redirect_response=False)

    @patch(f"{JH2_DISPLAY}.student_access_check")
    def test_display_dispatcher_invalid_category_redirects(self, mock_access):
        """想定外カテゴリは problem_select へリダイレクト"""
        mock_access.return_value = self.student
        res = self._post_display_dispatcher(problem_category="invalid_category")

        expected = f"{self.url_problem_select}?student_id={self.student_id}&classroom_id={self.classroom_id}"
        self.assertRedirects(res, expected, fetch_redirect_response=False)

    # -------------------------
    # print dispatcher: カテゴリ検証
    # -------------------------
    @patch(f"{JH2_PRINT}.student_access_check")
    def test_print_dispatcher_missing_category_redirects(self, mock_access):
        """problem_category 未送信は problem_select へリダイレクト"""
        mock_access.return_value = self.student
        res = self._post_print_dispatcher(problem_category="")

        expected = f"{self.url_problem_select}?student_id={self.student_id}&classroom_id={self.classroom_id}"
        self.assertRedirects(res, expected, fetch_redirect_response=False)

    @patch(f"{JH2_PRINT}.student_access_check")
    def test_print_dispatcher_invalid_category_redirects(self, mock_access):
        """想定外カテゴリは problem_select へリダイレクト"""
        mock_access.return_value = self.student
        res = self._post_print_dispatcher(problem_category="invalid_category")

        expected = f"{self.url_problem_select}?student_id={self.student_id}&classroom_id={self.classroom_id}"
        self.assertRedirects(res, expected, fetch_redirect_response=False)

    # -------------------------
    # display view GET: セッション欠落
    # -------------------------
    @patch(f"{JH2_DISPLAY}.student_access_check")
    def test_simul_display_missing_session_redirects(self, mock_access):
        """セッションに equation_types/used_coefficients/answer_types がない場合、problem_select へリダイレクト"""
        mock_access.return_value = self.student

        s = self.client.session
        for k in ("equation_types", "used_coefficients", "answer_types"):
            s.pop(k, None)
        s.save()

        res = self.client.get(
            self.url_simul_display,
            data={"student_id": self.student_id, "classroom_id": self.classroom_id},
        )

        expected = f"{self.url_problem_select}?student_id={self.student_id}&classroom_id={self.classroom_id}"
        self.assertRedirects(res, expected, fetch_redirect_response=False)
