from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from math_trainer.constraints.common import ALLOWED_PAPER_NUMBERS


# 例）math_trainer.views.elementary2.print_views / math_trainer.elementary2.print_views など
PRINT_VIEWS_MODULE = "math_trainer.views.elementary2.print_views"
DISPLAY_VIEWS_MODULE = "math_trainer.views.elementary2.display_views"


class Elementary2PrintViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u1", password="pass")
        self.client.force_login(self.user)

        # student_access_check が返すダミー student
        self.student = SimpleNamespace(id=123)

        self.student_id = str(self.student.id)
        self.classroom_id = "456"

        self.url_dispatcher_print = reverse("math_trainer:elementary2:dispatcher_print")
        self.url_problem_select = reverse("math_trainer:elementary2:problem_select")
        self.url_clock_print = reverse("math_trainer:elementary2:clock_print")

    def _post_dispatcher_clock(self, **overrides):
        """
        dispatcher_print に clock のPOSTを投げるヘルパ
        """
        data = {
            "student_id": self.student_id,
            "classroom_id": self.classroom_id,
            "problem_category": "clock",
            "paper_number": "5",
            "problem_type": ["read_time"],
            "width_of_time": ["greater_than_or_equal_to_one_hour"],
        }
        data.update(overrides)
        return self.client.post(self.url_dispatcher_print, data=data)

    @patch(f"{PRINT_VIEWS_MODULE}.student_access_check")
    def test_dispatcher_requires_login(self, mock_access):
        # ログイン必須の最低保証（LoginRequiredMixin）
        self.client.logout()
        res = self._post_dispatcher_clock()
        self.assertEqual(res.status_code, 302)
        # login_url は環境により異なるため、パス断定は避ける
        mock_access.assert_not_called()

    @patch(f"{PRINT_VIEWS_MODULE}.student_access_check")
    def test_dispatcher_invalid_paper_number_redirects_to_problem_select(self, mock_access):
        mock_access.return_value = self.student

        # paper_number が欠落 or 不正 → problem_select へ戻す
        res = self._post_dispatcher_clock(paper_number="9999")  # 許可制なら None になる想定
        self.assertEqual(res.status_code, 302)

        # build_url が student_id/classroom_id をクエリに付ける想定
        self.assertIn(self.url_problem_select, res["Location"])

    @patch(f"{PRINT_VIEWS_MODULE}.student_access_check")
    def test_dispatcher_missing_problem_types_redirects(self, mock_access):
        mock_access.return_value = self.student

        res = self._post_dispatcher_clock(problem_type=[])
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_problem_select, res["Location"])

    @patch(f"{PRINT_VIEWS_MODULE}.student_access_check")
    def test_dispatcher_missing_widths_redirects(self, mock_access):
        mock_access.return_value = self.student

        res = self._post_dispatcher_clock(width_of_time=[])
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_problem_select, res["Location"])

    @patch(f"{PRINT_VIEWS_MODULE}.student_access_check")
    def test_dispatcher_success_sets_session_and_redirects_to_clock_print(self, mock_access):
        mock_access.return_value = self.student

        res = self._post_dispatcher_clock(paper_number="5")
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_clock_print, res["Location"])

        # session に値が入っていること
        session = self.client.session
        self.assertEqual(session.get("paper_number"), 5)
        self.assertEqual(session.get("problem_types"), ["read_time"])
        self.assertEqual(session.get("widths_of_time"), ["greater_than_or_equal_to_one_hour"])

    @patch(f"{PRINT_VIEWS_MODULE}.student_access_check")
    def test_clock_print_missing_session_values_redirects(self, mock_access):
        """
        ClockPrintView: sessionが欠落していると problem_select に戻す
        """
        mock_access.return_value = self.student

        # session を空にする
        session = self.client.session
        session.pop("paper_number", None)
        session.pop("problem_types", None)
        session.pop("widths_of_time", None)
        session.save()

        res = self.client.get(self.url_clock_print, data={"student_id": self.student_id, "classroom_id": self.classroom_id})
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_problem_select, res["Location"])

    @patch(f"{PRINT_VIEWS_MODULE}.shape_two_columns.group_into_tuples")
    @patch(f"{PRINT_VIEWS_MODULE}.problem_generator.problem_generator")
    @patch(f"{PRINT_VIEWS_MODULE}.student_access_check")
    def test_clock_print_success_renders_pages(self, mock_access, mock_problem_generator, mock_group_into_tuples):
        """
        ClockPrintView: 正常系で paper_number 枚分の pages を作る
        generator/DB に依存させず、problem_generator を mock する。
        """
        mock_access.return_value = self.student

        # session 前提を満たす
        session = self.client.session
        paper_number = min(ALLOWED_PAPER_NUMBERS)
        session["paper_number"] = paper_number
        session["problem_types"] = ["read_time"]
        session["widths_of_time"] = ["greater_than_or_equal_to_one_hour"]
        session.save()

        # problem_generator が返す problems と session(id)
        fake_problems = [SimpleNamespace(id=i) for i in range(6)]
        fake_session = SimpleNamespace(id=999)

        mock_problem_generator.return_value = (fake_problems, fake_session)
        mock_group_into_tuples.return_value = [("p0", "p1"), ("p2", "p3"), ("p4", "p5")]

        res = self.client.get(self.url_clock_print, data={"student_id": self.student_id, "classroom_id": self.classroom_id})
        self.assertEqual(res.status_code, 200)

        # contextにpages があり、paper_number枚ぶん生成されている
        pages = res.context["pages"]
        self.assertEqual(len(pages), paper_number)
        self.assertEqual(res.context["paper_number"], paper_number)

        # generatorが指定回呼ばれたこと（紙枚数ぶん）
        self.assertEqual(mock_problem_generator.call_count, paper_number)

class Elementary2DisplayViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u1", password="pass")
        self.client.force_login(self.user)

        # student_access_check が返すダミー student
        self.student = SimpleNamespace(id=123)
        self.student_id = str(self.student.id)
        self.classroom_id = "456"

        self.url_dispatcher_display = reverse("math_trainer:elementary2:dispatcher_display")
        self.url_problem_select = reverse("math_trainer:elementary2:problem_select")
        self.url_clock_display = reverse("math_trainer:elementary2:clock_display")
        self.url_clock_result = reverse("math_trainer:elementary2:clock_result")

    def _post_dispatcher_clock(self, **overrides):
        data = {
            "student_id": self.student_id,
            "classroom_id": self.classroom_id,
            "problem_category": "clock",
            "problem_type": ["read_time"],
            "width_of_time": ["greater_than_or_equal_to_one_hour"],
        }
        data.update(overrides)
        return self.client.post(self.url_dispatcher_display, data=data)

    @patch(f"{DISPLAY_VIEWS_MODULE}.student_access_check")
    def test_display_dispatcher_requires_login(self, mock_access):
        self.client.logout()
        res = self._post_dispatcher_clock()
        self.assertEqual(res.status_code, 302)
        mock_access.assert_not_called()

    @patch(f"{DISPLAY_VIEWS_MODULE}.student_access_check")
    def test_display_dispatcher_missing_problem_types_redirects(self, mock_access):
        mock_access.return_value = self.student

        res = self._post_dispatcher_clock(problem_type=[])
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_problem_select, res["Location"])

    @patch(f"{DISPLAY_VIEWS_MODULE}.student_access_check")
    def test_display_dispatcher_missing_widths_redirects(self, mock_access):
        mock_access.return_value = self.student

        res = self._post_dispatcher_clock(width_of_time=[])
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_problem_select, res["Location"])

    @patch(f"{DISPLAY_VIEWS_MODULE}.student_access_check")
    def test_display_dispatcher_success_sets_session_and_redirects(self, mock_access):
        mock_access.return_value = self.student

        res = self._post_dispatcher_clock()
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_clock_display, res["Location"])

        session = self.client.session
        self.assertEqual(session.get("problem_types"), ["read_time"])
        self.assertEqual(session.get("widths_of_time"), ["greater_than_or_equal_to_one_hour"])

    @patch(f"{DISPLAY_VIEWS_MODULE}.shape_two_columns.group_into_tuples")
    @patch(f"{DISPLAY_VIEWS_MODULE}.problem_generator.problem_generator")
    @patch(f"{DISPLAY_VIEWS_MODULE}.student_access_check")
    def test_clock_display_get_success_renders(self, mock_access, mock_problem_generator, mock_group):
        """
        GET 正常系：session値が揃っていてレンダリングされる
        """
        mock_access.return_value = self.student

        session = self.client.session
        session["problem_types"] = ["read_time"]
        session["widths_of_time"] = ["greater_than_or_equal_to_one_hour"]
        session.save()

        fake_problems = [SimpleNamespace(id=i) for i in range(6)]
        fake_session = SimpleNamespace(id=999)

        mock_problem_generator.return_value = (fake_problems, fake_session)
        mock_group.return_value = [("p0", "p1"), ("p2", "p3"), ("p4", "p5")]

        res = self.client.get(self.url_clock_display, data={"student_id": self.student_id, "classroom_id": self.classroom_id})
        self.assertEqual(res.status_code, 200)
        self.assertIn("problem_session_id", res.context)

    @patch(f"{DISPLAY_VIEWS_MODULE}.student_access_check")
    def test_clock_display_get_missing_session_redirects(self, mock_access):
        """
        GET 異常系：session値が欠落していると problem_select に戻す
        """
        mock_access.return_value = self.student

        session = self.client.session
        session.pop("problem_types", None)
        session.pop("widths_of_time", None)
        session.save()

        res = self.client.get(self.url_clock_display, data={"student_id": self.student_id, "classroom_id": self.classroom_id})
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_problem_select, res["Location"])

    @patch(f"{DISPLAY_VIEWS_MODULE}.ProblemInstance")
    @patch(f"{DISPLAY_VIEWS_MODULE}.session_access_check")
    @patch(f"{DISPLAY_VIEWS_MODULE}.student_access_check")
    def test_clock_display_post_sets_result_and_redirects(self, mock_access, mock_session_access, mock_problem_instance_model):
        """
        POST：採点処理の“枠”だけ確認（DBはmock）
        - ProblemInstance.objects.filter(...).order_by('id') を差し替え
        - session_access_check の戻りも差し替え
        """
        mock_access.return_value = self.student
        fake_session = SimpleNamespace(id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        mock_session_access.return_value = fake_session

        # Fake instances
        inst1 = SimpleNamespace(id=1, choice_texts=["A", "B"], answer_text="A", metadata={})
        inst2 = SimpleNamespace(id=2, choice_texts=["C", "D"], answer_text="D", metadata={})
        qs = SimpleNamespace(order_by=lambda *args, **kwargs: [inst1, inst2])
        mock_problem_instance_model.objects.filter.return_value = qs

        # q_1=0 (A) 正解 / q_2=1 (D) 正解
        post_data = {
            "problem_session_id": str(fake_session.id),
            "q_1": "0",
            "q_2": "1",
        }
        res = self.client.post(
            self.url_clock_display + f"?student_id={self.student_id}&classroom_id={self.classroom_id}",
            data=post_data,
        )
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_clock_result, res["Location"])

        # session に math_quiz_result が積まれている
        s = self.client.session
        data = s.get("math_quiz_result")
        self.assertIsNotNone(data)
        self.assertEqual(data["summary"]["correct"], 2)
        self.assertEqual(data["summary"]["total"], 2)

    @patch(f"{DISPLAY_VIEWS_MODULE}.ProblemInstance")
    @patch(f"{DISPLAY_VIEWS_MODULE}.session_access_check")
    @patch(f"{DISPLAY_VIEWS_MODULE}.student_access_check")
    def test_clock_result_view_no_session_data_redirects_to_index(self, mock_access, mock_session_access, mock_problem_instance_model):
        """
        result：sessionに結果が無い場合は index に戻る
        """
        mock_access.return_value = self.student

        # 結果データを入れない
        s = self.client.session
        s.pop("math_quiz_result", None)
        s.save()

        res = self.client.get(self.url_clock_result, data={"student_id": self.student_id, "classroom_id": self.classroom_id})
        self.assertEqual(res.status_code, 302)  # index へ
        