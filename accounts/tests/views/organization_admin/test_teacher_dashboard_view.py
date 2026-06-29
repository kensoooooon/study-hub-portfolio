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


class TeacherDashboardViewTest(TestCase):
    """
    講師用ダッシュボードのテスト

    Developing:
        組織管理者、教室管理者、生徒は403
        未ログインユーザーはログインにnext付きでリダイレクト
        講師は自身の担当生徒は含まれるが、他人の担当生徒、未所属生徒などは見られない
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
            username="student1",
            email="target_student1@example.com",
            password="pass123456",
            line_user_id="target_student1_line_id",
            organization=cls.org,
        )
        cls.target_student1.classrooms.add(cls.classroom1)
        cls.target_student1.teachers.add(cls.teacher)

        # チェック対象生徒(教室外+組織内)
        cls.target_student2 = Student.objects.create_user(
            username="student2",
            email="target_student2@example.com",
            password="pass123456",
            line_user_id="target_student2_line_id",
            organization=cls.org,
        )
        cls.target_student2.classrooms.add(cls.classroom2)

        # チェック対象生徒(教室所属+組織外)
        cls.target_student3 = Student.objects.create_user(
            username="student3",
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

        cls.url_to_teacher_dashboard = reverse("organization_admin:teacher_dashboard")

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
    
    def test_org_admin_cannot_access_by_get(self):
        """
        組織管理者はgetでアクセス不可
        """
        self.login_as_org_admin()
        resp = self.client.get(self.url_to_teacher_dashboard)
        self.assertEqual(resp.status_code, 403)
    
    def test_org_admin_cannot_access_by_post(self):
        """
        組織管理者はpostでアクセス不可
        """
        self.login_as_org_admin()
        resp = self.client.post(self.url_to_teacher_dashboard)
        self.assertEqual(resp.status_code, 405)

    def test_classroom_admin_cannot_access_by_get(self):
        """
        教室管理者はgetでアクセス不可
        """
        self.login_as_class_admin()
        resp = self.client.get(self.url_to_teacher_dashboard)
        self.assertEqual(resp.status_code, 403)

    def test_classroom_admin_cannot_access_by_post(self):
        """
        教室管理者はpostでアクセス不可
        """
        self.login_as_class_admin()
        resp = self.client.post(self.url_to_teacher_dashboard)
        self.assertEqual(resp.status_code, 405)
    
    def test_teacher_can_access_by_get(self):
        """
        教室管理者はgetでアクセス可
        """
        self.login_as_teacher()
        resp = self.client.get(self.url_to_teacher_dashboard)
        self.assertEqual(resp.status_code, 200)

    def test_classroom_admin_can_access_by_post(self):
        """
        教室管理者はpostでアクセス不可
        """
        self.login_as_teacher()
        resp = self.client.post(self.url_to_teacher_dashboard)
        self.assertEqual(resp.status_code, 405)
    
    def test_student_cannot_access_by_get(self):
        """
        生徒はgetでアクセス不可
        """
        self.login_as_student_user()
        resp = self.client.get(self.url_to_teacher_dashboard)
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_access_by_post(self):
        """
        生徒はpostでアクセス不可
        """
        self.login_as_student_user()
        resp = self.client.post(self.url_to_teacher_dashboard)
        self.assertEqual(resp.status_code, 405)
    
    def test_anonymous_user_is_redirected_to_login(self):
        """
        未ログインユーザーはログイン画面にリダイレクト
        """
        resp = self.client.get(self.url_to_teacher_dashboard)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts_auth:login"), resp.url)

    # 正常系
    def test_teacher_can_see_assigned_students(self):
        """
        講師は担当生徒を見ることができる
        """
        self.login_as_teacher()
        resp = self.client.get(self.url_to_teacher_dashboard)
        self.assertIn(self.target_student1, resp.context["students"])

    def test_teacher_cannot_see_inactive_assigned_student(self):
        """
        講師は無効化された担当生徒を見られない
        """
        self.target_student4.teachers.add(self.teacher)
        self.login_as_teacher()

        resp = self.client.get(self.url_to_teacher_dashboard)

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(self.target_student4, resp.context["students"])

    def test_teacher_cannot_see_unassigned_student_in_same_organization(self):
        """
        講師は同一組織でも担当外生徒は見られない
        """
        self.login_as_teacher()

        resp = self.client.get(self.url_to_teacher_dashboard)

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(self.target_student2, resp.context["students"])

    def test_teacher_cannot_see_student_in_other_organization(self):
        """
        講師は他組織の生徒を見られない

        このテスト怪しくない？
        """
        self.target_student3.teachers.add(self.teacher)  # 万一M2Mがついても見えないことを確認
        self.login_as_teacher()

        resp = self.client.get(self.url_to_teacher_dashboard)

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(self.target_student3, resp.context["students"])

    def test_teacher_can_see_only_all_assigned_active_students(self):
        """
        講師は担当中の有効な生徒のみ見られる
        """
        target_student5 = Student.objects.create_user(
            username="student5",
            email="target_student5@example.com",
            password="pass123456",
            line_user_id="target_student5_line_id",
            organization=self.org,
        )
        target_student5.teachers.add(self.teacher)

        self.login_as_teacher()
        resp = self.client.get(self.url_to_teacher_dashboard)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.target_student1, resp.context["students"])
        self.assertIn(target_student5, resp.context["students"])
        self.assertNotIn(self.target_student2, resp.context["students"])
        self.assertNotIn(self.target_student4, resp.context["students"])

    def test_teacher_dashboard_returns_expected_students_count(self):
        """
        講師ダッシュボードには期待した人数だけ表示される
        """
        self.login_as_teacher()
        resp = self.client.get(self.url_to_teacher_dashboard)

        self.assertEqual(resp.status_code, 200)
        self.assertQuerySetEqual(
            resp.context["students"].order_by("id"),
            [self.target_student1],
            transform=lambda x: x,
            ordered=False,
        )

    def test_teacher_dashboard_students_are_ordered_by_grade(self):
        """
        講師ダッシュボードの生徒は学年順に並ぶ
        """
        self.target_student1.grade = 10
        self.target_student1.save()

        target_student5 = Student.objects.create_user(
            username="student5",
            email="target_student5@example.com",
            password="pass123456",
            line_user_id="target_student5_line_id",
            organization=self.org,
            grade=7,
        )
        target_student5.teachers.add(self.teacher)

        self.login_as_teacher()
        resp = self.client.get(self.url_to_teacher_dashboard)

        students = list(resp.context["students"])
        self.assertEqual(students, [self.target_student1, target_student5])
