from urllib.parse import urlparse, parse_qs


from django.test import TestCase
from django.urls import reverse
from django.contrib.messages import get_messages


from accounts.models import (
    Organization,
    Classroom,
    OrganizationAdministrator,
    ClassroomAdministrator,
    Teacher,
    Student,
)


class ClassroomAssignmentViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Org")
        cls.classroom1 = Classroom.objects.create(name="Class1", organization=cls.org)
        cls.classroom2 = Classroom.objects.create(name="Class2", organization=cls.org)

        cls.other_org = Organization.objects.create(name="OtherOrg")
        cls.other_classroom = Classroom.objects.create(
            name="OtherOrgClass",
            organization=cls.other_org,
        )

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
            username="teacher_user",
            password="pass123456",
            role="teacher",
            organization=cls.org,
            is_first_login=False,
        )
        cls.teacher.classrooms.add(cls.classroom1)

        cls.student_user = Student.objects.create_user(
            email="student_user@example.com",
            username="student_user",
            password="pass123456",
            role="student",
            line_user_id="student_user_line_id",
            organization=cls.org,
            is_first_login=False,
        )
        cls.student_user.classrooms.add(cls.classroom1)

        # 正常に割り当てる対象
        cls.unassigned_student = Student.objects.create_user(
            email="unassigned_student@example.com",
            username="unassigned_student",
            password="pass123456",
            role="student",
            line_user_id="unassigned_student_line_id",
            organization=cls.org,
        )

        # 候補から除外されるべき生徒たち
        cls.inactive_student = Student.objects.create_user(
            email="inactive_student@example.com",
            username="inactive_student",
            password="pass123456",
            role="student",
            line_user_id="inactive_student_line_id",
            organization=cls.org,
            is_active=False,
        )

        cls.no_line_student = Student.objects.create_user(
            email="no_line_student@example.com",
            username="no_line_student",
            password="pass123456",
            role="student",
            line_user_id=None,
            organization=cls.org,
        )

        cls.assigned_student = Student.objects.create_user(
            email="assigned_student@example.com",
            username="assigned_student",
            password="pass123456",
            role="student",
            line_user_id="assigned_student_line_id",
            organization=cls.org,
        )
        cls.assigned_student.classrooms.add(cls.classroom1)

        cls.other_org_student = Student.objects.create_user(
            email="other_org_student@example.com",
            username="other_org_student",
            password="pass123456",
            role="student",
            line_user_id="other_org_student_line_id",
            organization=cls.other_org,
        )

        cls.url = reverse(
            "organization_admin:assign_classroom",
            kwargs={"pk": cls.unassigned_student.pk},
        )
        cls.success_url = reverse("organization_admin:unassigned_students")

    def login_as_org_admin(self):
        ok = self.client.login(email="org_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_class_admin(self):
        ok = self.client.login(email="class_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_teacher(self):
        ok = self.client.login(email="teacher@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_student(self):
        ok = self.client.login(email="student_user@example.com", password="pass123456")
        self.assertTrue(ok)

    def test_anonymous_user_is_redirected_to_login(self):
        """
        未ログインユーザーはログイン画面にリダイレクト
        """
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts_auth:login"), resp.url)

    def test_org_admin_can_access(self):
        """
        組織管理者はアクセス可能
        """
        self.login_as_org_admin()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_class_admin_cannot_access(self):
        """
        教室管理者はアクセス不可
        """
        self.login_as_class_admin()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_teacher_cannot_access(self):
        """
        講師はアクセス不可
        """
        self.login_as_teacher()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_access(self):
        """
        生徒はアクセス不可
        """
        self.login_as_student()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_org_admin_can_assign_unassigned_student(self):
        """
        組織管理者は教室に割り当てられない生徒を割り当てることが可能
        """
        self.login_as_org_admin()

        resp = self.client.post(
            self.url,
            data={
                "student": str(self.unassigned_student.pk),
                "classroom": self.classroom1.pk,
            },
        )

        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, self.success_url)

        self.unassigned_student.refresh_from_db()
        self.assertTrue(
            self.unassigned_student.classrooms.filter(pk=self.classroom1.pk).exists()
        )

        messages = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(
            any("教室に割り当てました" in message for message in messages)
        )

    def test_get_shows_only_assignable_students(self):
        """
        getでアクセスした際に表示される生徒は、割り当て可能な生徒だけ
        """
        self.login_as_org_admin()

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

        form = resp.context["form"]
        student_qs = form.fields["student"].queryset
        classroom_qs = form.fields["classroom"].queryset

        self.assertIn(self.unassigned_student, student_qs)  # 未割り当て生徒は含まれる
        self.assertNotIn(self.inactive_student, student_qs)  # 無効化された生徒は含まれない
        self.assertNotIn(self.no_line_student, student_qs)  # LINEユーザーIDが存在しない生徒は含まれない
        self.assertNotIn(self.assigned_student, student_qs)  # 割り当て済みの生徒は含まれない
        self.assertNotIn(self.other_org_student, student_qs)  # 自分の組織でない生徒は含まれない

        self.assertIn(self.classroom1, classroom_qs)
        self.assertIn(self.classroom2, classroom_qs)
        self.assertNotIn(self.other_classroom, classroom_qs)

    def test_post_with_other_org_student_is_rejected(self):
        """
        他の組織の生徒が編集されることはない
        """
        self.login_as_org_admin()

        resp = self.client.post(
            self.url,
            data={
                "student": str(self.other_org_student.pk),
                "classroom": self.classroom1.pk,
            },
        )

        self.assertEqual(resp.status_code, 200)  # 表示自体はされるが、データが不正
        form = resp.context["form"]
        self.assertTrue(form.errors)

        self.other_org_student.refresh_from_db()
        self.assertFalse(
            self.other_org_student.classrooms.filter(pk=self.classroom1.pk).exists()
        )

    def test_post_with_inactive_student_is_rejected(self):
        """
        無効化された生徒は割り当てられない
        """
        self.login_as_org_admin()

        resp = self.client.post(
            self.url,
            data={
                "student": str(self.inactive_student.pk),
                "classroom": self.classroom1.pk,
            },
        )

        self.assertEqual(resp.status_code, 200)
        form = resp.context["form"]
        self.assertTrue(form.errors)

        self.inactive_student.refresh_from_db()
        self.assertFalse(
            self.inactive_student.classrooms.filter(pk=self.classroom1.pk).exists()
        )

    def test_post_with_other_org_classroom_is_rejected(self):
        """
        他の組織の教室の生徒は割り当てられない
        """
        self.login_as_org_admin()

        resp = self.client.post(
            self.url,
            data={
                "student": str(self.unassigned_student.pk),
                "classroom": self.other_classroom.pk,
            },
        )

        self.assertEqual(resp.status_code, 200)
        form = resp.context["form"]
        self.assertTrue(form.errors)

        self.unassigned_student.refresh_from_db()
        self.assertFalse(
            self.unassigned_student.classrooms.filter(pk=self.other_classroom.pk).exists()
        )

    def test_post_with_assigned_student_is_rejected(self):
        """
        割り当て済みの生徒は割り当てられない
        """
        self.login_as_org_admin()

        resp = self.client.post(
            self.url,
            data={
                "student": str(self.assigned_student.pk),
                "classroom": self.classroom2.pk,
            },
        )

        self.assertEqual(resp.status_code, 200)
        form = resp.context["form"]
        self.assertTrue(form.errors)

        self.assigned_student.refresh_from_db()
        self.assertFalse(
            self.assigned_student.classrooms.filter(pk=self.classroom2.pk).exists()
        )
    
    def test_student_cannot_post_assignment(self):
        """
        dispatchが有効であり、生徒によるPOSTでのアクセスは無効化される
        """
        self.login_as_student()
        resp = self.client.post(
            self.url,
            data={
                "student": str(self.unassigned_student.pk),
                "classroom": self.classroom1.pk,
            },
        )
        self.assertEqual(resp.status_code, 403)

        self.unassigned_student.refresh_from_db()
        self.assertFalse(
            self.unassigned_student.classrooms.filter(pk=self.classroom1.pk).exists()
        )


    def test_teacher_cannot_post_assignment(self):
        """
        dispatchが有効であり、講師によるPOSTでのアクセスは無効化される
        """
        self.login_as_teacher()
        resp = self.client.post(
            self.url,
            data={
                "student": str(self.unassigned_student.pk),
                "classroom": self.classroom1.pk,
            },
        )
        self.assertEqual(resp.status_code, 403)

        self.unassigned_student.refresh_from_db()
        self.assertFalse(
            self.unassigned_student.classrooms.filter(pk=self.classroom1.pk).exists()
        )

    def test_class_admin_cannot_post_assignment(self):
        """
        dispatchが有効であり、教室管理者によるPOSTでのアクセスは無効化される
        """
        self.login_as_class_admin()
        resp = self.client.post(
            self.url,
            data={
                "student": str(self.unassigned_student.pk),
                "classroom": self.classroom1.pk,
            },
        )
        self.assertEqual(resp.status_code, 403)

        self.unassigned_student.refresh_from_db()
        self.assertFalse(
            self.unassigned_student.classrooms.filter(pk=self.classroom1.pk).exists()
        )

    def test_anonymous_user_is_redirected_to_login_with_next(self):
        """
        未ログインユーザーはnextのパラメータ付きでログイン画面に飛ばされる
        """
        resp = self.client.get(self.url)

        self.assertEqual(resp.status_code, 302)

        parsed = urlparse(resp.url)
        self.assertEqual(parsed.path, reverse("accounts_auth:login"))

        query = parse_qs(parsed.query)
        self.assertEqual(query.get("next"), [self.url])
