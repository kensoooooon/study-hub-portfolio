from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from accounts.models import (
Organization,
Classroom,
OrganizationAdministrator,
ClassroomAdministrator,
Teacher,
Student,
)



class StudentDetailViewTest(TestCase):
    """
    生徒詳細ビューのテスト

    Developing:
        anonymous は 302
        student ロールは 403
        teacher: 担当生徒 200
        teacher: 担当外生徒 404
        classroom admin: 自教室生徒 200
        classroom admin: 教室外生徒 404
        organization admin: 同一組織の複数生徒を 200 で取得できる
        inactive student は 404
        あれば十分
        organization admin: 同一組織の別教室生徒も 200
    """

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Org")
        cls.classroom1 = Classroom.objects.create(name="Class1", organization=cls.org)
        cls.classroom2 = Classroom.objects.create(name="Class2", organization=cls.org)
        cls.other_org = Organization.objects.create(name="OtherOrg")

        # --- ログイン用ユーザー ---
        cls.org_admin = OrganizationAdministrator.objects.create_user(
            email="org_admin@example.com",
            username="org_admin",
            password="pass123456",
            role="organization_administrator",
        )
        cls.org_admin.organizations.add(cls.org)

        cls.class_admin = ClassroomAdministrator.objects.create_user(
            email="class_admin@example.com",
            username="class_admin",
            password="pass123456",
            role="classroom_administrator",
            organization=cls.org,
            is_first_login=False,
        )
        cls.class_admin.classrooms.add(cls.classroom1)

        cls.teacher = Teacher.objects.create_user(
            email="teacher@example.com",
            password="pass123456",
            organization=cls.org,
            is_first_login=False,
        )

        cls.student_user = Student.objects.create_user(
            email="student_user@example.com",
            password="pass123456",
            line_user_id="student_user_line_id",
            organization=cls.org,
            is_first_login=False,
        )

        # チェック対象生徒
        cls.target_student1 = Student.objects.create_user(
            email="target_student1@example.com",
            password="pass123456",
            line_user_id="target_student1_line_id",
            organization=cls.org,
        )
        cls.target_student1.classrooms.add(cls.classroom1)
        cls.target_student1.teachers.add(cls.teacher)

        # チェック対象生徒(教室外+組織内)
        cls.target_student2 = Student.objects.create_user(
            email="target_student2@example.com",
            password="pass123456",
            line_user_id="target_student2_line_id",
            organization=cls.org,
        )
        cls.target_student2.classrooms.add(cls.classroom2)

        # チェック対象生徒(教室所属+組織外)
        cls.target_student3 = Student.objects.create_user(
            email="target_student3@example.com",
            password="pass123456",
            line_user_id="target_student3_line_id",
            organization=cls.other_org,
        )

        cls.target_student4 = Student.objects.create_user(
            email="target_student4@example.com",
            password="pass123456",
            line_user_id="target_student4_line_id",
            organization=cls.org,
            is_active=False
        )

        # アクセスURL
        cls.url_to_target_student1_detail = reverse(
            "organization_admin:student_detail",
            kwargs={"pk": cls.target_student1.id}
        )
        cls.url_to_target_student2_detail = reverse(
            "organization_admin:student_detail",
            kwargs={"pk": cls.target_student2.id}
        )
        cls.url_to_target_student3_detail = reverse(
            "organization_admin:student_detail",
            kwargs={"pk": cls.target_student3.id}
        )
        cls.url_to_target_student4_detail = reverse(
            "organization_admin:student_detail",
            kwargs={"pk": cls.target_student4.id}
        )


    def login_as_org_admin(self):
        ok = self.client.login(email="org_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_class_admin(self):
        ok = self.client.login(email="class_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_teacher(self):
        ok = self.client.login(email="teacher@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_student_user(self):
        ok = self.client.login(email="student_user@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def logout_correctly(self):
        self.client.logout()

    def test_org_admin_can_access_all_students(self):
        """
        組織管理者は教室を問わず、自身の組織に所属している全ての生徒へアクセス可能
        """
        self.login_as_org_admin()
        urls = [self.url_to_target_student1_detail, self.url_to_target_student2_detail]
        for url in urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)
    
    def test_org_admin_cannot_access_other_org_students(self):
        """
        自身の組織に所属しない生徒へはアクセス不可
        """
        self.login_as_org_admin()
        resp = self.client.get(self.url_to_target_student3_detail)
        self.assertEqual(resp.status_code, 404)

    def test_class_admin_can_access_only_belonged_students(self):
        """
        教室管理者は自身の教室に所属している生徒のみアクセス可能
        """
        self.login_as_class_admin()
        resp = self.client.get(self.url_to_target_student1_detail)
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(self.url_to_target_student2_detail)
        self.assertEqual(resp.status_code, 404)
        resp = self.client.get(self.url_to_target_student3_detail)
        self.assertEqual(resp.status_code, 404)

    def test_teacher_can_access_only_assigned_students(self):
        """
        教師は自身の担当生徒のみアクセス可能
        """
        self.login_as_teacher()
        resp = self.client.get(self.url_to_target_student1_detail)
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(self.url_to_target_student2_detail)
        self.assertEqual(resp.status_code, 404)
        resp = self.client.get(self.url_to_target_student3_detail)
        self.assertEqual(resp.status_code, 404)

    def test_student_cannot_access_any_students(self):
        """
        生徒はいずれへも権限なしとして拒否
        """
        self.login_as_student_user()
        urls = [self.url_to_target_student1_detail, self.url_to_target_student2_detail, self.url_to_target_student3_detail, self.url_to_target_student4_detail]
        for url in urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 403)
    
    def test_inactive_student_cannot_be_accessed(self):
        """
        非アクティブになった生徒はいずれのユーザーからもアクセスされない
        """
        self.login_as_org_admin()
        resp = self.client.get(self.url_to_target_student4_detail)
        self.assertEqual(resp.status_code, 404)
        self.logout_correctly()
        self.login_as_class_admin()
        resp = self.client.get(self.url_to_target_student4_detail)
        self.assertEqual(resp.status_code, 404)
        self.logout_correctly()
        self.login_as_teacher()
        resp = self.client.get(self.url_to_target_student4_detail)
        self.assertEqual(resp.status_code, 404)
        self.logout_correctly()

    def test_anonymous_user_is_redirected_to_login(self):
        """
        未ログインユーザーはログインページにリダイレクトされる
        """
        resp = self.client.get(self.url_to_target_student1_detail)
        self.assertEqual(resp.status_code, 302)
        expected_url = f'{reverse("accounts_auth:login")}?next={self.url_to_target_student1_detail}'
        self.assertRedirects(resp, expected_url)

    @patch("accounts.views.organization_admin_views.has_vocab_progress")
    def test_has_vocab_progress_true_sets_has_vocab_history_context(self, mock_progress):
        """
        has_vocab_progress が True の場合、
        管理者詳細の has_vocab_history も True になる
        """
        self.login_as_org_admin()
        mock_progress.return_value = True

        resp = self.client.get(self.url_to_target_student1_detail)

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "accounts/organization_admin/student/detail.html")
        self.assertTrue(resp.context["has_vocab_history"])
        mock_progress.assert_called_once_with(self.target_student1)

    @patch("accounts.views.organization_admin_views.has_vocab_progress")
    def test_has_vocab_progress_false_sets_has_vocab_history_context(self, mock_progress):
        """
        has_vocab_progress が False の場合、
        管理者詳細の has_vocab_history も False になる
        """
        self.login_as_org_admin()
        mock_progress.return_value = False

        resp = self.client.get(self.url_to_target_student1_detail)

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "accounts/organization_admin/student/detail.html")
        self.assertFalse(resp.context["has_vocab_history"])
        mock_progress.assert_called_once_with(self.target_student1)
