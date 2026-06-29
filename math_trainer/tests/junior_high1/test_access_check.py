"""
中学1年生用ビューのアクセスチェック全般を実施
"""

from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from accounts.models import (
    OrganizationAdministrator,
    Organization,
    ClassroomAdministrator,
    Classroom,
    Teacher,
    Student
)
from math_trainer.utils.build_url import build_url


class ProblemSelectViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="org1")
        cls.org1_admin = OrganizationAdministrator.objects.create_user(
            username="org1_admin",
            email="org1_admin@example.com",
            password="pass123456"
        )
        cls.org1_admin.organizations.add(cls.org1)

        cls.class1_1 = Classroom.objects.create(name="class1_1", organization=cls.org1)
        cls.class1_1_admin = ClassroomAdministrator.objects.create_user(
            username="class1_1_admin",
            email="class1_1_admin@example.com",
            password="pass123456",
            organization=cls.org1,
            is_first_login=False,
        )
        cls.class1_1_admin.classrooms.add(cls.class1_1)
        cls.class1_1_teacher = Teacher.objects.create_user(
            username="class1_1_teacher",
            email="class1_1_teacher@example.com",
            password="pass123456",
            organization=cls.org1,
            is_first_login=False,
        )
        cls.class1_1_teacher.classrooms.add(cls.class1_1)

        cls.class1_1_active_student = Student.objects.create_user(
            username="class1_1_active_student",
            email="class1_1_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_1_active_student",
            is_first_login=False,
        )
        cls.class1_1_active_student.classrooms.add(cls.class1_1)
        cls.class1_1_active_student.teachers.add(cls.class1_1_teacher)

        cls.class1_1_inactive_student = Student.objects.create_user(
            username="class1_1_inactive_student",
            email="class1_1_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_1_inactive_student"
        )
        cls.class1_1_inactive_student.classrooms.add(cls.class1_1)
        cls.class1_1_inactive_student.teachers.add(cls.class1_1_teacher)

        cls.class1_2 = Classroom.objects.create(name="class1_2", organization=cls.org1)
        cls.class1_2_admin = ClassroomAdministrator.objects.create_user(
            username="class1_2_admin",
            email="class1_2_admin@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.class1_2_admin.classrooms.add(cls.class1_2)
        cls.class1_2_active_student = Student.objects.create_user(
            username="class1_2_active_student",
            email="class1_2_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_2_active_student"
        )
        cls.class1_2_active_student.classrooms.add(cls.class1_2)

        cls.org2 = Organization.objects.create(name="org2")
        cls.class2 = Classroom.objects.create(name="class2", organization=cls.org2)
        cls.class2_active_student = Student.objects.create_user(
            username="class2_active_student",
            email="class2_active_student@example.com",
            password="pass123456",
            organization=cls.org2,
            is_active=True,
            line_user_id="line_id_class2_active_student"
        )
        cls.class2_active_student.classrooms.add(cls.class2)

        cls.class2_inactive_student = Student.objects.create_user(
            username="class2_inactive_student",
            email="class2_inactive_student@example.com",
            password="pass123456",
            organization=cls.org2,
            is_active=False,
            line_user_id="line_id_class2_inactive_student"
        )
        cls.class2_inactive_student.classrooms.add(cls.class2)
    
    
    def login_as_classroom_admin(self):
        ok = self.client.login(email="class1_1_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_org_admin(self):
        ok = self.client.login(email="org1_admin@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_as_teacher(self):
        ok = self.client.login(email="class1_1_teacher@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_as_student(self):
        ok = self.client.login(email="class1_1_active_student@example.com", password="pass123456")
        self.assertTrue(ok)

    # --- Organization Admin ---

    def test_org_admin_can_access_student(self):
        """
        組織管理者は自身の管理している生徒にアクセス可能
        """
        self.login_as_org_admin()
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class1_1_active_student.id})
        self.assertEqual(resp.status_code, 200)


    def test_org_admin_cannot_access_another_org_student(self):
        """
        組織管理者は自身の管理していない組織の生徒にアクセス不可
        """
        self.login_as_org_admin()
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class2_active_student.id})
        self.assertEqual(resp.status_code, 403)


    def test_org_admin_cannot_access_inactive_student(self):
        """
        組織管理者は非アクティブ生徒へアクセス不可
        """
        self.login_as_org_admin()
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class1_1_inactive_student.id})
        self.assertEqual(resp.status_code, 404)


    @patch("accounts.models.BaseUser.get_role_object")
    def test_org_admin_returning_none_cannot_access(self, mock_role_object):
        """
        role_objectがNoneである組織管理者はアクセス不可
        """
        self.login_as_org_admin()
        mock_role_object.return_value = None
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class1_1_active_student.id})
        self.assertEqual(resp.status_code, 403)


    # --- Classroom Admin ---

    def test_classroom_admin_can_access_student(self):
        """
        教室管理者は自身の管理している教室に所属する生徒へアクセス可能
        """
        self.login_as_classroom_admin()
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class1_1_active_student.id})
        self.assertEqual(resp.status_code, 200)


    def test_classroom_admin_cannot_access_another_org_student(self):
        """
        教室管理者は他の組織の生徒にアクセス不可
        """
        self.login_as_classroom_admin()
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class2_active_student.id})
        self.assertEqual(resp.status_code, 403)


    def test_classroom_admin_cannot_access_another_classroom_student(self):
        """
        教室管理者は他の教室の生徒にアクセス不可
        """
        self.login_as_classroom_admin()
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class1_2_active_student.id})
        self.assertEqual(resp.status_code, 403)


    def test_classroom_admin_cannot_access_inactive_student(self):
        """
        教室管理者は非アクティブ生徒にアクセス不可
        """
        self.login_as_classroom_admin()
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class1_1_inactive_student.id})
        self.assertEqual(resp.status_code, 404)

    @patch("accounts.models.BaseUser.get_role_object")
    def test_classroom_admin_returning_none_cannot_access(self, mock_role_object):
        """
        role_objectがNoneである教室管理者はアクセス不可
        """
        self.login_as_classroom_admin()
        mock_role_object.return_value = None
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class1_1_active_student.id})
        self.assertEqual(resp.status_code, 403)


    # --- Teacher ---

    def test_teacher_can_access_student(self):
        """
        講師は担当生徒にアクセス可能
        """
        self.login_as_teacher()
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class1_1_active_student.id})
        self.assertEqual(resp.status_code, 200)


    def test_teacher_cannot_access_another_org_student(self):
        """
        講師は他の組織の生徒にアクセス不可
        """
        self.login_as_teacher()
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class2_active_student.id})
        self.assertEqual(resp.status_code, 403)


    def test_teacher_cannot_access_inactive_student(self):
        """
        講師はたとえ担当でも、非アクティブ生徒へアクセス不可
        """
        self.login_as_teacher()
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class1_1_inactive_student.id})
        self.assertEqual(resp.status_code, 404)

    @patch("accounts.models.BaseUser.get_role_object")
    def test_teacher_returning_none_cannot_access(self, mock_role_object):
        """
        role_objectがNoneである講師はアクセス不可
        """
        self.login_as_teacher()
        mock_role_object.return_value = None
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class1_1_active_student.id})
        self.assertEqual(resp.status_code, 403)


    # --- Student ---

    def test_student_can_access_self(self):
        """
        生徒は自分自身にアクセス可
        """
        self.login_as_student()
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class1_1_active_student.id})
        self.assertEqual(resp.status_code, 200)

    def test_student_cannot_access_any_other_student(self):
        """
        生徒は組織、教室に関わらず、他の生徒にアクセス不可
        """
        self.login_as_student()
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class1_2_active_student.id})
        self.assertEqual(resp.status_code, 403)
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class1_1_inactive_student.id})
        self.assertEqual(resp.status_code, 403)
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class2_active_student.id})
        self.assertEqual(resp.status_code, 403)
        url = reverse("math_trainer:junior_high1:problem_select")
        resp = self.client.get(url, data={"student_id": self.class2_inactive_student.id})
        self.assertEqual(resp.status_code, 403)


class JuniorHigh1DisplayDispatcherViewTest(TestCase):
    """
    小学2年生の割り当てビュー用テスト

    Do:
        境界
        カテゴリー指定のありorなし
        問題タイプの指定ありorなし
        時間幅の指定ありorなし
        正常にアクセスした場合は動作あり
    """
    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="org1")
        cls.org1_admin = OrganizationAdministrator.objects.create_user(
            username="org1_admin",
            email="org1_admin@example.com",
            password="pass123456"
        )
        cls.org1_admin.organizations.add(cls.org1)

        cls.class1_1 = Classroom.objects.create(name="class1_1", organization=cls.org1)
        cls.class1_1_admin = ClassroomAdministrator.objects.create_user(
            username="class1_1_admin",
            email="class1_1_admin@example.com",
            password="pass123456",
            organization=cls.org1,
            is_first_login=False,
        )
        cls.class1_1_admin.classrooms.add(cls.class1_1)
        cls.class1_1_teacher = Teacher.objects.create_user(
            username="class1_1_teacher",
            email="class1_1_teacher@example.com",
            password="pass123456",
            organization=cls.org1,
            is_first_login=False,
        )
        cls.class1_1_teacher.classrooms.add(cls.class1_1)

        cls.class1_1_active_student = Student.objects.create_user(
            username="class1_1_active_student",
            email="class1_1_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_1_active_student",
            is_first_login=False,
        )
        cls.class1_1_active_student.classrooms.add(cls.class1_1)
        cls.class1_1_active_student.teachers.add(cls.class1_1_teacher)

        cls.class1_1_active_student_without_teacher = Student.objects.create_user(
            username="class1_1_active_student_without_teacher",
            email="class1_1_active_student_without_teacher@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_1_active_student_without_teacher"
        )
        cls.class1_1_active_student_without_teacher.classrooms.add(cls.class1_1)

        cls.class1_1_inactive_student = Student.objects.create_user(
            username="class1_1_inactive_student",
            email="class1_1_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_1_inactive_student"
        )
        cls.class1_1_inactive_student.classrooms.add(cls.class1_1)
        cls.class1_1_inactive_student.teachers.add(cls.class1_1_teacher)

        cls.class1_2 = Classroom.objects.create(name="class1_2", organization=cls.org1)
        cls.class1_2_admin = ClassroomAdministrator.objects.create_user(
            username="class1_2_admin",
            email="class1_2_admin@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.class1_2_admin.classrooms.add(cls.class1_2)
        cls.class1_2_active_student = Student.objects.create_user(
            username="class1_2_active_student",
            email="class1_2_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_2_active_student"
        )
        cls.class1_2_active_student.classrooms.add(cls.class1_2)

        cls.org2 = Organization.objects.create(name="org2")
        cls.class2 = Classroom.objects.create(name="class2", organization=cls.org2)
        cls.class2_active_student = Student.objects.create_user(
            username="class2_active_student",
            email="class2_active_student@example.com",
            password="pass123456",
            organization=cls.org2,
            is_active=True,
            line_user_id="line_id_class2_active_student"
        )
        cls.class2_active_student.classrooms.add(cls.class2)

        cls.class2_inactive_student = Student.objects.create_user(
            username="class2_inactive_student",
            email="class2_inactive_student@example.com",
            password="pass123456",
            organization=cls.org2,
            is_active=False,
            line_user_id="line_id_class2_inactive_student"
        )
        cls.class2_inactive_student.classrooms.add(cls.class2)
    
    def access_to_junior_high1_dispatcher(self, parms):
        url = reverse("math_trainer:junior_high1:dispatcher_display")
        resp = self.client.post(url, data=parms)
        return resp
    
    def login_as_classroom_admin(self):
        ok = self.client.login(email="class1_1_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_org_admin(self):
        ok = self.client.login(email="org1_admin@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_as_teacher(self):
        ok = self.client.login(email="class1_1_teacher@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_as_student(self):
        ok = self.client.login(email="class1_1_active_student@example.com", password="pass123456")
        self.assertTrue(ok)

    def test_anonymous_user_redirect_to_login(self):
        """
        未ログインユーザーは必要な情報があってもログイン画面へリダイレクト
        """
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("accounts_auth:login"))
    
    def test_org_admin_can_access(self):
        """
        組織管理者は自身の管理組織に所属した生徒相手に正しい情報があればアクセス可能で、解答画面へ遷移
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        expected_url = build_url(
            reverse("math_trainer:junior_high1:specific_linear_equation_display"),
            self.class1_1_active_student.id,
            self.class1_1.id,
        )
        self.assertRedirects(resp, expected_url)

    def test_classroom_admin_can_access(self):
        """
        教室管理者は自身の管理している教室に所属した生徒相手に正しい情報があればアクセス可能で、解答画面へ遷移
        """
        self.login_as_classroom_admin()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        expected_url = build_url(
            reverse("math_trainer:junior_high1:specific_linear_equation_display"),
            self.class1_1_active_student.id,
            self.class1_1.id,
        )
        self.assertRedirects(resp, expected_url)

    def test_teacher_can_access(self):
        """
        講師は担当している生徒相手に正しい情報があればアクセス可能で、解答画面へ遷移
        """
        self.login_as_teacher()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        expected_url = build_url(
            reverse("math_trainer:junior_high1:specific_linear_equation_display"),
            self.class1_1_active_student.id,
            self.class1_1.id,
        )
        self.assertRedirects(resp, expected_url)

    def test_student_can_access(self):
        """
        生徒は自分自身に正しい情報があればアクセス可能で、解答画面へ遷移
        """
        self.login_as_student()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        expected_url = build_url(
            reverse("math_trainer:junior_high1:specific_linear_equation_display"),
            self.class1_1_active_student.id,
            self.class1_1.id,
        )
        self.assertRedirects(resp, expected_url)

    def test_org_admin_cannot_access_another_org_student(self):
        """
        組織管理者は自身の管理組織に所属していない生徒へアクセス不可
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class2_active_student.id,
            "classroom_id": self.class2.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)

    def test_classroom_admin_cannot_access_another_org_and_another_classroom_student(self):
        """
        教室管理者は他の組織の生徒、および自組織他教室の生徒にアクセス不可

        """
        self.login_as_classroom_admin()
        data = {
            "student_id": self.class2_active_student.id,
            "classroom_id": self.class2.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)
        data = {
            "student_id": self.class1_2_active_student.id,
            "classroom_id": self.class1_2.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)

    def test_teacher_cannot_access_another_org_and_another_classroom_student(self):
        """
        講師は他の組織の生徒、および自組織他教室でも担当でない生徒にアクセス不可
        """
        self.login_as_teacher()
        data = {
            "student_id": self.class2_active_student.id,
            "classroom_id": self.class2.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)
        data = {
            "student_id": self.class1_2_active_student.id,
            "classroom_id": self.class1_2.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)
        data = {
            "student_id": self.class1_1_active_student_without_teacher.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_access_except_for_self(self):
        """
        生徒は自分自身を除いてアクセス不可
        """
        self.login_as_student()
        data = {
            "student_id": self.class2_active_student.id,
            "classroom_id": self.class2.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)
        data = {
            "student_id": self.class1_2_active_student.id,
            "classroom_id": self.class1_2.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)
        data = {
            "student_id": self.class1_1_active_student_without_teacher.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)
    
    @patch("accounts.models.BaseUser.get_role_object")
    def test_user_without_role_object_cannot_access(self, mock_role_object):
        """
        role_objectが正常に取得できないユーザーはアクセス不可
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class1_1_active_student,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        mock_role_object.return_value = None
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)
    
    def test_org_admin_cannot_inactive_student(self):
        """
        組織管理者は非アクティブ生徒にアクセス不可
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class1_1_inactive_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 404)

    def test_classroom_admin_cannot_inactive_student(self):
        """
        教室管理者は非アクティブ生徒にアクセス不可
        """
        self.login_as_classroom_admin()
        data = {
            "student_id": self.class1_1_inactive_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 404)

    def test_teacher_cannot_inactive_student(self):
        """
        講師は非アクティブ生徒にアクセス不可
        """
        self.login_as_teacher()
        data = {
            "student_id": self.class1_1_inactive_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 404)

    def test_invalid_category_redirect_to_problem_select(self):
        """
        存在しない問題カテゴリは問題選択へリダイレクト
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "invalid",
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 302)
        expected = build_url(reverse("math_trainer:junior_high1:problem_select"), self.class1_1_active_student.id, self.class1_1.id)
        self.assertRedirects(resp, expected)

    def test_missing_problem_type_redirect(self):
        """
        問題タイプが指定されていない場合はリダイレクト
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "width_of_time": ["less_than_one_hour"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 302)
        expected = build_url(reverse("math_trainer:junior_high1:problem_select"), self.class1_1_active_student.id, self.class1_1.id)
        self.assertRedirects(resp, expected)

    
    def test_missing_number_to_use_redirect(self):
        """
        優先的に使用する係数が指定されていない場合はリダイレクト
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 302)
        expected = build_url(reverse("math_trainer:junior_high1:problem_select"), self.class1_1_active_student.id, self.class1_1.id)
        self.assertRedirects(resp, expected)

    def test_missing_problem_category_redirect_to_problem_select(self):
        """
        カテゴリーが存在しない場合は問題選択へリダイレクト
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_type": ["read_time"],
            "width_of_time": ["less_than_one_hour"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 302)
        expected = build_url(reverse("math_trainer:junior_high1:problem_select"), self.class1_1_active_student.id, self.class1_1.id)
        self.assertRedirects(resp, expected)


class JuniorHigh1PrintDispatcherViewTest(TestCase):
    """
    小学2年生の割り当てビュー用テスト

    Do:
        境界
        カテゴリー指定のありorなし
        問題タイプの指定ありorなし
        時間幅の指定ありorなし
        正常にアクセスした場合は動作あり
    """
    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="org1")
        cls.org1_admin = OrganizationAdministrator.objects.create_user(
            username="org1_admin",
            email="org1_admin@example.com",
            password="pass123456"
        )
        cls.org1_admin.organizations.add(cls.org1)

        cls.class1_1 = Classroom.objects.create(name="class1_1", organization=cls.org1)
        cls.class1_1_admin = ClassroomAdministrator.objects.create_user(
            username="class1_1_admin",
            email="class1_1_admin@example.com",
            password="pass123456",
            organization=cls.org1,
            is_first_login=False,
        )
        cls.class1_1_admin.classrooms.add(cls.class1_1)
        cls.class1_1_teacher = Teacher.objects.create_user(
            username="class1_1_teacher",
            email="class1_1_teacher@example.com",
            password="pass123456",
            organization=cls.org1,
            is_first_login=False,
        )
        cls.class1_1_teacher.classrooms.add(cls.class1_1)

        cls.class1_1_active_student = Student.objects.create_user(
            username="class1_1_active_student",
            email="class1_1_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_1_active_student",
            is_first_login=False,
        )
        cls.class1_1_active_student.classrooms.add(cls.class1_1)
        cls.class1_1_active_student.teachers.add(cls.class1_1_teacher)

        cls.class1_1_active_student_without_teacher = Student.objects.create_user(
            username="class1_1_active_student_without_teacher",
            email="class1_1_active_student_without_teacher@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_1_active_student_without_teacher"
        )
        cls.class1_1_active_student_without_teacher.classrooms.add(cls.class1_1)

        cls.class1_1_inactive_student = Student.objects.create_user(
            username="class1_1_inactive_student",
            email="class1_1_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_1_inactive_student"
        )
        cls.class1_1_inactive_student.classrooms.add(cls.class1_1)
        cls.class1_1_inactive_student.teachers.add(cls.class1_1_teacher)

        cls.class1_2 = Classroom.objects.create(name="class1_2", organization=cls.org1)
        cls.class1_2_admin = ClassroomAdministrator.objects.create_user(
            username="class1_2_admin",
            email="class1_2_admin@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.class1_2_admin.classrooms.add(cls.class1_2)
        cls.class1_2_active_student = Student.objects.create_user(
            username="class1_2_active_student",
            email="class1_2_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_2_active_student"
        )
        cls.class1_2_active_student.classrooms.add(cls.class1_2)

        cls.org2 = Organization.objects.create(name="org2")
        cls.class2 = Classroom.objects.create(name="class2", organization=cls.org2)
        cls.class2_active_student = Student.objects.create_user(
            username="class2_active_student",
            email="class2_active_student@example.com",
            password="pass123456",
            organization=cls.org2,
            is_active=True,
            line_user_id="line_id_class2_active_student"
        )
        cls.class2_active_student.classrooms.add(cls.class2)

        cls.class2_inactive_student = Student.objects.create_user(
            username="class2_inactive_student",
            email="class2_inactive_student@example.com",
            password="pass123456",
            organization=cls.org2,
            is_active=False,
            line_user_id="line_id_class2_inactive_student"
        )
        cls.class2_inactive_student.classrooms.add(cls.class2)
    
    def access_to_junior_high1_dispatcher(self, parms):
        url = reverse("math_trainer:junior_high1:dispatcher_print")
        resp = self.client.post(url, data=parms)
        return resp
    
    def login_as_classroom_admin(self):
        ok = self.client.login(email="class1_1_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_org_admin(self):
        ok = self.client.login(email="org1_admin@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_as_teacher(self):
        ok = self.client.login(email="class1_1_teacher@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_as_student(self):
        ok = self.client.login(email="class1_1_active_student@example.com", password="pass123456")
        self.assertTrue(ok)

    def test_anonymous_user_redirect_to_login(self):
        """
        未ログインユーザーは必要な情報があってもログイン画面へリダイレクト
        """
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("accounts_auth:login"))
    
    def test_org_admin_can_access(self):
        """
        組織管理者は自身の管理組織に所属した生徒相手に正しい情報があればアクセス可能で、解答画面へ遷移
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        expected_url = build_url(
            reverse("math_trainer:junior_high1:specific_linear_equation_print"),
            self.class1_1_active_student.id,
            self.class1_1.id,
        )
        self.assertRedirects(resp, expected_url)

    def test_classroom_admin_can_access(self):
        """
        教室管理者は自身の管理している教室に所属した生徒相手に正しい情報があればアクセス可能で、解答画面へ遷移
        """
        self.login_as_classroom_admin()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        expected_url = build_url(
            reverse("math_trainer:junior_high1:specific_linear_equation_print"),
            self.class1_1_active_student.id,
            self.class1_1.id,
        )
        self.assertRedirects(resp, expected_url)

    def test_teacher_can_access(self):
        """
        講師は担当している生徒相手に正しい情報があればアクセス可能で、解答画面へ遷移
        """
        self.login_as_teacher()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        expected_url = build_url(
            reverse("math_trainer:junior_high1:specific_linear_equation_print"),
            self.class1_1_active_student.id,
            self.class1_1.id,
        )
        self.assertRedirects(resp, expected_url)

    def test_student_can_access(self):
        """
        生徒は自分自身に正しい情報があればアクセス可能で、解答画面へ遷移
        """
        self.login_as_student()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        expected_url = build_url(
            reverse("math_trainer:junior_high1:specific_linear_equation_print"),
            self.class1_1_active_student.id,
            self.class1_1.id,
        )
        self.assertRedirects(resp, expected_url)

    def test_org_admin_cannot_access_another_org_student(self):
        """
        組織管理者は自身の管理組織に所属していない生徒へアクセス不可
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class2_active_student.id,
            "classroom_id": self.class2.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)

    def test_classroom_admin_cannot_access_another_org_and_another_classroom_student(self):
        """
        教室管理者は他の組織の生徒、および自組織他教室の生徒にアクセス不可

        """
        self.login_as_classroom_admin()
        data = {
            "student_id": self.class2_active_student.id,
            "classroom_id": self.class2.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)
        data = {
            "student_id": self.class1_2_active_student.id,
            "classroom_id": self.class1_2.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)

    def test_teacher_cannot_access_another_org_and_another_classroom_student(self):
        """
        講師は他の組織の生徒、および自組織他教室でも担当でない生徒にアクセス不可
        """
        self.login_as_teacher()
        data = {
            "student_id": self.class2_active_student.id,
            "classroom_id": self.class2.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)
        data = {
            "student_id": self.class1_2_active_student.id,
            "classroom_id": self.class1_2.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)
        data = {
            "student_id": self.class1_1_active_student_without_teacher.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_access_except_for_self(self):
        """
        生徒は自分自身を除いてアクセス不可
        """
        self.login_as_student()
        data = {
            "student_id": self.class2_active_student.id,
            "classroom_id": self.class2.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)
        data = {
            "student_id": self.class1_2_active_student.id,
            "classroom_id": self.class1_2.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)
        data = {
            "student_id": self.class1_1_active_student_without_teacher.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)
    
    @patch("accounts.models.BaseUser.get_role_object")
    def test_user_without_role_object_cannot_access(self, mock_role_object):
        """
        role_objectが正常に取得できないユーザーはアクセス不可
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class1_1_active_student,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        mock_role_object.return_value = None
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 403)
    
    def test_org_admin_cannot_inactive_student(self):
        """
        組織管理者は非アクティブ生徒にアクセス不可
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class1_1_inactive_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 404)

    def test_classroom_admin_cannot_inactive_student(self):
        """
        教室管理者は非アクティブ生徒にアクセス不可
        """
        self.login_as_classroom_admin()
        data = {
            "student_id": self.class1_1_inactive_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 404)

    def test_teacher_cannot_inactive_student(self):
        """
        講師は非アクティブ生徒にアクセス不可
        """
        self.login_as_teacher()
        data = {
            "student_id": self.class1_1_inactive_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            "number_to_use": ["integer", "decimal"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 404)

    def test_invalid_category_redirect_to_problem_select(self):
        """
        存在しない問題カテゴリは問題選択へリダイレクト
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "paper_number": "5",
            "problem_category": "invalid",
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 302)
        expected = build_url(reverse("math_trainer:junior_high1:problem_select"), self.class1_1_active_student.id, self.class1_1.id)
        self.assertRedirects(resp, expected)

    def test_missing_problem_type_redirect(self):
        """
        問題タイプが指定されていない場合はリダイレクト
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            # problem_typeなし
            "width_of_time": ["less_than_one_hour"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 302)
        expected = build_url(reverse("math_trainer:junior_high1:problem_select"), self.class1_1_active_student.id, self.class1_1.id)
        self.assertRedirects(resp, expected)

    
    def test_missing_number_to_use_redirect(self):
        """
        優先的に使用する係数が指定されていない場合はリダイレクト
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "5",
            "problem_type": ["ax_equal_b_only_integer", "ax_equal_b_all_number"],
            # width_of_timeなし
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 302)
        expected = build_url(reverse("math_trainer:junior_high1:problem_select"), self.class1_1_active_student.id, self.class1_1.id)
        self.assertRedirects(resp, expected)

    def test_missing_problem_category_redirect_to_problem_select(self):
        """
        カテゴリーが存在しない場合は問題選択へリダイレクト
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            # categoryなし
            "paper_number": "5",
            "problem_type": ["read_time"],
            "width_of_time": ["less_than_one_hour"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 302)
        expected = build_url(reverse("math_trainer:junior_high1:problem_select"), self.class1_1_active_student.id, self.class1_1.id)
        self.assertRedirects(resp, expected)
    
    def test_missing_paper_number_redirect_to_problem_select(self):
        """
        プリントの枚数が存在しない場合は問題選択へリダイレクト
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "problem_type": ["read_time"],
            "width_of_time": ["less_than_one_hour"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 302)
        expected = build_url(reverse("math_trainer:junior_high1:problem_select"), self.class1_1_active_student.id, self.class1_1.id)
        self.assertRedirects(resp, expected)

    def test_not_allowed_paper_number_redirect_to_problem_select(self):
        """
        プリントの枚数が存在しない場合は問題選択へリダイレクト
        """
        self.login_as_org_admin()
        data = {
            "student_id": self.class1_1_active_student.id,
            "classroom_id": self.class1_1.id,
            "problem_category": "specific_linear_equation",
            "paper_number": "8",
            "problem_type": ["read_time"],
            "width_of_time": ["less_than_one_hour"],
        }
        resp = self.access_to_junior_high1_dispatcher(data)
        self.assertEqual(resp.status_code, 302)
        expected = build_url(reverse("math_trainer:junior_high1:problem_select"), self.class1_1_active_student.id, self.class1_1.id)
        self.assertRedirects(resp, expected)
