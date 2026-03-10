from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from math_trainer.constraints import ALLOWED_PAPER_NUMBERS


# ★ここだけ要調整（あなたのプロジェクトの実パスに合わせる）
PATCH_MODULE_PRINT = "math_trainer.views.junior_high1.print_views"
PATCH_MODULE_DISPLAY = "math_trainer.views.junior_high1.display_views"


class JuniorHigh1PrintViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u1", password="pass")
        self.client.force_login(self.user)

        self.student = SimpleNamespace(id=123)
        self.student_id = str(self.student.id)
        self.classroom_id = "456"

        self.url_dispatcher_print = reverse("math_trainer:junior_high1:dispatcher_print")
        self.url_problem_select = reverse("math_trainer:junior_high1:problem_select")
        self.url_specific_linear_print = reverse("math_trainer:junior_high1:specific_linear_equation_print")

        # 設定追従（将来変更してもテストが壊れにくい）
        self.allowed_paper_number = min(ALLOWED_PAPER_NUMBERS)

    def _post_dispatcher(self, **overrides):
        data = {
            "student_id": self.student_id,
            "classroom_id": self.classroom_id,
            "problem_category": "specific_linear_equation",
            "paper_number": str(self.allowed_paper_number),
            "problem_type": ["dummy_type"],      # 内容は view が空チェックのみならこれでOK
            "number_to_use": ["dummy_number"],   # 同上
        }
        data.update(overrides)
        return self.client.post(self.url_dispatcher_print, data=data)

    @patch(f"{PATCH_MODULE_PRINT}.student_access_check")
    def test_print_dispatcher_requires_login(self, mock_access):
        self.client.logout()
        res = self._post_dispatcher()
        self.assertEqual(res.status_code, 302)
        mock_access.assert_not_called()

    @patch(f"{PATCH_MODULE_PRINT}.student_access_check")
    def test_print_dispatcher_invalid_paper_number_redirects(self, mock_access):
        mock_access.return_value = self.student

        res = self._post_dispatcher(paper_number="9999")  # allowed外
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_problem_select, res["Location"])

    @patch(f"{PATCH_MODULE_PRINT}.student_access_check")
    def test_print_dispatcher_missing_problem_type_redirects(self, mock_access):
        mock_access.return_value = self.student

        res = self._post_dispatcher(problem_type=[])
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_problem_select, res["Location"])

    @patch(f"{PATCH_MODULE_PRINT}.student_access_check")
    def test_print_dispatcher_missing_number_to_use_redirects(self, mock_access):
        mock_access.return_value = self.student

        res = self._post_dispatcher(number_to_use=[])
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_problem_select, res["Location"])

    @patch(f"{PATCH_MODULE_PRINT}.student_access_check")
    def test_print_dispatcher_success_sets_session_and_redirects(self, mock_access):
        mock_access.return_value = self.student

        res = self._post_dispatcher()
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_specific_linear_print, res["Location"])

        session = self.client.session
        self.assertEqual(session.get("paper_number"), self.allowed_paper_number)
        self.assertEqual(session.get("problem_types"), ["dummy_type"])
        self.assertEqual(session.get("numbers_to_use"), ["dummy_number"])

    @patch(f"{PATCH_MODULE_PRINT}.student_access_check")
    def test_specific_linear_print_missing_session_redirects(self, mock_access):
        mock_access.return_value = self.student

        session = self.client.session
        session.pop("paper_number", None)
        session.pop("problem_types", None)
        session.pop("numbers_to_use", None)
        session.save()

        res = self.client.get(
            self.url_specific_linear_print,
            data={"student_id": self.student_id, "classroom_id": self.classroom_id},
        )
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_problem_select, res["Location"])

    @patch(f"{PATCH_MODULE_PRINT}.shape_two_columns.group_into_tuples")
    @patch(f"{PATCH_MODULE_PRINT}.problem_generator.problem_generator")
    @patch(f"{PATCH_MODULE_PRINT}.student_access_check")
    def test_specific_linear_print_success_renders_pages(self, mock_access, mock_problem_generator, mock_group):
        mock_access.return_value = self.student

        session = self.client.session
        session["paper_number"] = self.allowed_paper_number
        session["problem_types"] = ["dummy_type"]
        session["numbers_to_use"] = ["dummy_number"]
        session.save()

        fake_problems = [SimpleNamespace(id=i) for i in range(10)]
        fake_session = SimpleNamespace(id=999)

        mock_problem_generator.return_value = (fake_problems, fake_session)
        mock_group.return_value = [("p0", "p1"), ("p2", "p3"), ("p4", "p5"), ("p6", "p7"), ("p8", "p9")]

        res = self.client.get(
            self.url_specific_linear_print,
            data={"student_id": self.student_id, "classroom_id": self.classroom_id},
        )
        self.assertEqual(res.status_code, 200)

        pages = res.context["pages"]
        self.assertEqual(len(pages), self.allowed_paper_number)
        self.assertEqual(res.context["paper_number"], self.allowed_paper_number)

        self.assertEqual(mock_problem_generator.call_count, self.allowed_paper_number)


class JuniorHigh1DisplayViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u1", password="pass")
        self.client.force_login(self.user)

        self.student = SimpleNamespace(id=123)
        self.student_id = str(self.student.id)
        self.classroom_id = "456"

        self.url_dispatcher_display = reverse("math_trainer:junior_high1:dispatcher_display")
        self.url_problem_select = reverse("math_trainer:junior_high1:problem_select")
        self.url_specific_linear_display = reverse("math_trainer:junior_high1:specific_linear_equation_display")

    def _post_dispatcher(self, **overrides):
        data = {
            "student_id": self.student_id,
            "classroom_id": self.classroom_id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["dummy_type"],
            "number_to_use": ["dummy_number"],
        }
        data.update(overrides)
        return self.client.post(self.url_dispatcher_display, data=data)

    @patch(f"{PATCH_MODULE_DISPLAY}.student_access_check")
    def test_display_dispatcher_requires_login(self, mock_access):
        self.client.logout()
        res = self._post_dispatcher()
        self.assertEqual(res.status_code, 302)
        mock_access.assert_not_called()

    @patch(f"{PATCH_MODULE_DISPLAY}.student_access_check")
    def test_display_dispatcher_missing_problem_type_redirects(self, mock_access):
        mock_access.return_value = self.student
        res = self._post_dispatcher(problem_type=[])
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_problem_select, res["Location"])

    @patch(f"{PATCH_MODULE_DISPLAY}.student_access_check")
    def test_display_dispatcher_missing_numbers_redirects(self, mock_access):
        mock_access.return_value = self.student
        res = self._post_dispatcher(number_to_use=[])
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_problem_select, res["Location"])

    @patch(f"{PATCH_MODULE_DISPLAY}.student_access_check")
    def test_display_dispatcher_success_redirects(self, mock_access):
        mock_access.return_value = self.student
        res = self._post_dispatcher()
        self.assertEqual(res.status_code, 302)
        self.assertIn(self.url_specific_linear_display, res["Location"])

        session = self.client.session
        self.assertEqual(session.get("problem_types"), ["dummy_type"])
        self.assertEqual(session.get("numbers_to_use"), ["dummy_number"])

    @patch(f"{PATCH_MODULE_DISPLAY}.shape_two_columns.group_into_tuples")
    @patch(f"{PATCH_MODULE_DISPLAY}.problem_generator.problem_generator")
    @patch(f"{PATCH_MODULE_DISPLAY}.student_access_check")
    def test_specific_linear_display_get_success(self, mock_access, mock_problem_generator, mock_group):
        """
        GET正常系：sessionに必要値があり、問題生成が走って表示される
        """
        mock_access.return_value = self.student

        session = self.client.session
        session["problem_types"] = ["dummy_type"]
        session["numbers_to_use"] = ["dummy_number"]
        session.save()

        fake_problems = [SimpleNamespace(id=i) for i in range(10)]
        fake_session = SimpleNamespace(id=888)
        mock_problem_generator.return_value = (fake_problems, fake_session)
        mock_group.return_value = [("p0", "p1")]  # 形は何でもOK（テンプレ依存を避ける）

        res = self.client.get(
            self.url_specific_linear_display,
            data={"student_id": self.student_id, "classroom_id": self.classroom_id},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("problem_session_id", res.context)
