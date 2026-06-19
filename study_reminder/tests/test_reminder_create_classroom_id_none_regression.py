"""
回帰テスト: ReminderCreateView における classroom_id=None / 未指定 の防止

【背景】
study_reminder の ReminderCreateView は get_context_data 内で
GET パラメータから classroom_id を取得してテンプレートに渡す。
classroom_id=None（文字列）が来た場合に正規化せず context に渡すと、
テンプレートの戻るリンクが ?classroom_id=None を含む URL を生成し、
次画面で NoReverseMatch → 500 になる可能性があった。

【修正内容】
get_context_data 内で classroom_id == 'None' を Python None に正規化。

【このテストの目的】
上記修正の回帰防止。classroom_id 未指定・"None" 文字列のいずれでも
ReminderCreateView が 200 を返し、context の classroom_id が汚染されないことを保証する。
"""

from django.test import TestCase
from django.urls import reverse

from accounts.models import (
    Organization,
    Classroom,
    OrganizationAdministrator,
    ClassroomAdministrator,
    Teacher,
    Student,
)


class ReminderCreateViewClassroomIdRegressionTest(TestCase):
    """
    ReminderCreateView: classroom_id 未指定 / "None" でも 500 にならないことを確認する。
    """

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="ReminderRegressionOrg")
        cls.classroom = Classroom.objects.create(name="ReminderRegressionClass", organization=cls.org)

        cls.org_admin = OrganizationAdministrator.objects.create_user(
            email="reminder_regression_org_admin@example.com",
            username="reminder_regression_org_admin",
            password="pass123456",
            role="organization_administrator",
            is_first_login=False
        )
        cls.org_admin.organizations.add(cls.org)

        cls.class_admin = ClassroomAdministrator.objects.create_user(
            email="reminder_regression_class_admin@example.com",
            username="reminder_regression_class_admin",
            password="pass123456",
            role="classroom_administrator",
            organization=cls.org,
            is_first_login=False,
        )
        cls.class_admin.classrooms.add(cls.classroom)

        cls.teacher = Teacher.objects.create_user(
            email="reminder_regression_teacher@example.com",
            username="reminder_regression_teacher",
            password="pass123456",
            organization=cls.org,
            is_first_login=False,
        )
        cls.teacher.classrooms.add(cls.classroom)

        cls.target_student = Student.objects.create_user(
            email="reminder_regression_target@example.com",
            username="reminder_regression_target",
            password="pass123456",
            line_user_id="reminder_regression_target_line_id",
            organization=cls.org,
        )
        cls.target_student.classrooms.add(cls.classroom)
        cls.target_student.teachers.add(cls.teacher)

    def _create_url(self, student_id=None, classroom_id=None):
        url = reverse("reminder_create")
        params = []
        if student_id is not None:
            params.append(f"student={student_id}")
        if classroom_id is not None:
            params.append(f"classroom_id={classroom_id}")
        if params:
            url += "?" + "&".join(params)
        return url

    def login_as(self, email, password="pass123456"):
        ok = self.client.login(email=email, password=password)
        self.assertTrue(ok, f"ログイン失敗: {email}")

    # --- org_admin ---

    def test_org_admin_no_classroom_id_returns_200(self):
        """classroom_id 未指定でも 200"""
        self.login_as("reminder_regression_org_admin@example.com")
        url = self._create_url(student_id=self.target_student.pk)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_org_admin_classroom_id_none_string_returns_200(self):
        """classroom_id=None（文字列）でも 500 にならない"""
        self.login_as("reminder_regression_org_admin@example.com")
        url = self._create_url(student_id=self.target_student.pk, classroom_id="None")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_org_admin_classroom_id_none_string_not_in_context(self):
        """
        classroom_id=None（文字列）が来たとき、context に classroom_id が
        セットされないこと（None は if ブロックを通過しないため）。
        """
        self.login_as("reminder_regression_org_admin@example.com")
        url = self._create_url(student_id=self.target_student.pk, classroom_id="None")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # classroom_id が None に正規化され context にセットされていないことを確認
        self.assertNotIn("classroom_id", resp.context)

    def test_org_admin_valid_classroom_id_returns_200(self):
        """正常な classroom_id が渡された場合も 200 かつ context にセットされる（正常系）"""
        self.login_as("reminder_regression_org_admin@example.com")
        url = self._create_url(student_id=self.target_student.pk, classroom_id=self.classroom.pk)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(str(resp.context["classroom_id"]), str(self.classroom.pk))

    # --- class_admin ---

    def test_class_admin_no_classroom_id_returns_200(self):
        """教室管理者: classroom_id 未指定でも 200"""
        self.login_as("reminder_regression_class_admin@example.com")
        url = self._create_url(student_id=self.target_student.pk)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_class_admin_classroom_id_none_string_returns_200(self):
        """教室管理者: classroom_id=None（文字列）でも 500 にならない"""
        self.login_as("reminder_regression_class_admin@example.com")
        url = self._create_url(student_id=self.target_student.pk, classroom_id="None")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    # --- teacher ---

    def test_teacher_no_classroom_id_returns_200(self):
        """講師: classroom_id なしが通常導線。200 を返すこと"""
        self.login_as("reminder_regression_teacher@example.com")
        url = self._create_url(student_id=self.target_student.pk)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_teacher_classroom_id_none_string_returns_200(self):
        """講師: classroom_id=None（文字列）でも 500 にならない"""
        self.login_as("reminder_regression_teacher@example.com")
        url = self._create_url(student_id=self.target_student.pk, classroom_id="None")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
