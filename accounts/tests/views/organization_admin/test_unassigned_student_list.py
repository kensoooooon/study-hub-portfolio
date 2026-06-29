"""
UnassignedStudentsListViewのテスト

- 組織管理者がアクセスしたとき、
    - 自身の組織かつ教室に所属している->表示されない
    - 自身の組織かつ教室に所属していない->表示される
    - 他者の組織かつ教室に所属している->表示されない
    - 他者の組織かつ教室に所属していない->表示される
    - 非アクティブだとカウントされない
- 組織管理者以外では一律弾かれる
"""
from django.test import TestCase
from django.urls import reverse

from accounts.models import (
    Student,
    Teacher,
    ClassroomAdministrator,
    OrganizationAdministrator,
    Classroom,
    Organization
)


class UnassignedStudentListTest(TestCase):
    """
    未割り当て生徒がアクティブ状態とテナント境界により、正しく表示されることを確認
    """

    @classmethod
    def setUpTestData(cls):
        # 対象生徒が所属している組織と管理者
        cls.org1 = Organization.objects.create(name="Organization 1")
        cls.org_admin1 = OrganizationAdministrator.objects.create_user(
            username="Org Admin1",
            email="org_admin1@example.com",
            password="pass123456",
        )
        cls.org_admin1.organizations.add(cls.org1)

        # 組織に所属している教室と管理者
        cls.classroom1 = Classroom.objects.create(name="ClassRoom 1", organization=cls.org1)
        cls.classroom_admin1 = ClassroomAdministrator.objects.create_user(
            username="Classroom Admin1",
            email="classroom_admin1@example.com",
            password="pass123456",
            organization=cls.org1,
            is_first_login=False,
        )
        cls.classroom_admin1.classrooms.add(cls.classroom1)
        
        # 同じ組織で、対象を担当している講師
        cls.teacher1 = Teacher.objects.create_user(
            username="Teacher1",
            email="teacher1@example.com",
            password="pass123456",
            organization=cls.org1,
            is_first_login=False,
        )
        cls.teacher1.classrooms.add(cls.classroom1)

        # 組織と教室に属している生徒
        cls.student1 = Student.objects.create_user(
            username="Visible Expected Student",
            email="student1@example.com",
            password="pass123456",
            organization=cls.org1,
            line_user_id="line_user_id_student1",
            is_first_login=False,
        )
        cls.student1.classrooms.add(cls.classroom1)
        cls.student1.teachers.add(cls.teacher1)

        # 組織には属しているが、教室には属していない生徒
        cls.student1_2 = Student.objects.create_user(
            username="Not Visible Student",
            email="student1_2@example.com",
            password="pass123456",
            organization=cls.org1,
            line_user_id="line_user_id_student1_2",
        )
        cls.student1_2.teachers.add(cls.teacher1)


        # 別組織と管理者
        cls.org2 = Organization.objects.create(name="Organization 2")
        cls.org_admin2 = OrganizationAdministrator.objects.create_user(
            username="Org Admin2",
            email="org_admin2@example.com",
            password="pass123456",
        )
        cls.org_admin2.organizations.add(cls.org2)

        # 別組織の教室と管理者
        cls.classroom2 = Classroom.objects.create(name="ClassRoom 2", organization=cls.org2)
        cls.classroom_admin2 = ClassroomAdministrator.objects.create_user(
            username="Classroom Admin2",
            email="classroom_admin2@example.com",
            password="pass123456",
            organization=cls.org2,
        )
        cls.classroom_admin2.classrooms.add(cls.classroom2)

        # 別組織の教師
        cls.teacher2 = Teacher.objects.create_user(
            username="Teacher2",
            email="teacher2@example.com",
            password="pass123456",
            organization=cls.org2,
        )
        cls.teacher2.classrooms.add(cls.classroom2)

        # 他組織の教室に属している生徒
        cls.student2 = Student.objects.create_user(
            username="Sample Student2",
            email="student2@example.com",
            password="pass123456",
            organization=cls.org2,
            line_user_id="line_user_id_student2",
        )
        cls.student2.classrooms.add(cls.classroom2)
        cls.student2.teachers.add(cls.teacher2)

        # 他組織の教室に属していない生徒
        cls.student2_2 = Student.objects.create_user(
            username="Sample Student2_2",
            email="student2_2@example.com",
            password="pass123456",
            organization=cls.org2,
            line_user_id="line_user_id_student2_2",
        )
        cls.student2_2.teachers.add(cls.teacher2)

    def login_student1(self):
        ok = self.client.login(email="student1@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_teacher1(self):
        ok = self.client.login(email="teacher1@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_classroom_admin1(self):
        ok = self.client.login(email="classroom_admin1@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_org_admin1(self):
        ok = self.client.login(email="org_admin1@example.com", password="pass123456")
        self.assertTrue(ok)

    def test_student_cannot_access(self):
        """
        生徒はアクセス不可
        """
        self.login_student1()
        url = reverse("organization_admin:unassigned_students")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_teacher_cannot_access(self):
        """
        講師はアクセス不可
        """
        self.login_teacher1()
        url = reverse("organization_admin:unassigned_students")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
    
    def test_classroom_admin_cannot_access(self):
        """
        教室管理者はアクセス不可
        """
        self.login_classroom_admin1()
        url = reverse("organization_admin:unassigned_students")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
    
    def test_same_tenant_org_admin_can_access(self):
        """
        組織管理者は自組織の教室未割り当て生徒を確認可能
        """
        self.login_org_admin1()
        url = reverse("organization_admin:unassigned_students")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)  # アクセス可
        self.assertNotContains(response, f"<td>{self.student1.username}</td>", html=True)  # 教室に割り当てられている生徒は見えない
        self.assertContains(response, f"<td>{self.student1_2.username}</td>", html=True)  # 割り当てられていない生徒は見える
        self.assertNotContains(response, f"<td>{self.student2.username}</td>", html=True)  # 他組織は、割り当てのあるなし関係無しに見えない
        self.assertNotContains(response, f"<td>{self.student2_2.username}</td>", html=True)

    def test_anonymous_user_is_redirected_to_login(self):
        """
        未ログインユーザーはログイン画面へ飛ばされる(LoginRequiredMixin確認)
        """
        url = reverse("organization_admin:unassigned_students")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts_auth:login"), response.url)

    def test_inactive_same_tenant_unassigned_student_is_not_shown(self):
        """
        非アクティブの生徒は未割り当て生徒には表示されない
        """
        self.student1_2.is_active = False
        self.student1_2.save(update_fields=["is_active"])

        self.login_org_admin1()
        response = self.client.get(reverse("organization_admin:unassigned_students"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f"<td>{self.student1_2.username}</td>", html=True)

    def test_same_tenant_unassigned_student_without_line_user_id_is_not_shown(self):
        """
        LINEユーザーIDが存在しない生徒は表示されない
        """
        student = Student.objects.create_user(
            username="No Line Student",
            email="no_line_student@example.com",
            password="pass123456",
            organization=self.org1,
            line_user_id=None,
        )
        student.teachers.add(self.teacher1)

        self.login_org_admin1()
        response = self.client.get(reverse("organization_admin:unassigned_students"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f"<td>{student.username}</td>", html=True)

    def test_multiple_same_tenant_unassigned_students_are_shown(self):
        """
        複数の未所属生徒がいた場合、そちらも表示される
        """
        student3 = Student.objects.create_user(
            username="Another Unassigned Student",
            email="student3@example.com",
            password="pass123456",
            organization=self.org1,
            line_user_id="line_user_id_student3",
        )
        student3.teachers.add(self.teacher1)

        self.login_org_admin1()
        response = self.client.get(reverse("organization_admin:unassigned_students"))

        self.assertContains(response, f"<td>{self.student1_2.username}</td>", html=True)
        self.assertContains(response, f"<td>{student3.username}</td>", html=True)

    def test_org_admin_sees_only_expected_unassigned_students_count(self):
        """
        組織管理者が期待した生徒だけ見れているか
        """
        self.login_org_admin1()
        response = self.client.get(reverse("organization_admin:unassigned_students"))

        students = list(response.context["students"])
        self.assertEqual(len(students), 1)
        self.assertEqual(students[0], self.student1_2)

    def test_context_students_do_not_include_other_tenant_students(self):
        """
        他の組織の生徒が混入しないか
        """
        self.login_org_admin1()
        response = self.client.get(reverse("organization_admin:unassigned_students"))

        students = list(response.context["students"])
        self.assertIn(self.student1_2, students)
        self.assertNotIn(self.student2, students)
        self.assertNotIn(self.student2_2, students)

    def test_unassigned_org_admin_cannot_see_anything(self):
        """
        組織が割り当てられていない組織管理者は、取得するデータが0になる
        """
        unassigned_org = OrganizationAdministrator.objects.create_user(
            username="Unassigned Organization Administrator",
            email="unassigned_org_admin@example.com",
            password="pass123456"
        )
        ok = self.client.login(email="unassigned_org_admin@example.com", password="pass123456")
        self.assertTrue(ok)
        response = self.client.get(reverse("organization_admin:unassigned_students"))
        students = list(response.context["students"])
        self.assertEqual(len(students), 0)
