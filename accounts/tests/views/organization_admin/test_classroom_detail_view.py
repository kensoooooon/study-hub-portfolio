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


class ClassroomDetailViewTest(TestCase):

    def setUp(self):
        # --- 組織 ---
        self.org1 = Organization.objects.create(name="Org1")
        self.org2 = Organization.objects.create(name="Org2")

        # --- 教室 ---
        self.classroom1 = Classroom.objects.create(name="Class1", organization=self.org1)
        self.classroom2 = Classroom.objects.create(name="Class2", organization=self.org1)
        self.classroom_other_org = Classroom.objects.create(name="Class3", organization=self.org2)

        # --- ログイン用ユーザー ---
        self.org_admin = OrganizationAdministrator.objects.create_user(
            email="org_admin@example.com",
            username="org_admin",
            password="pass",
            role="organization_administrator",
        )
        self.class_admin = ClassroomAdministrator.objects.create_user(
            email="class_admin@example.com",
            username="class_admin",
            password="pass",
            role="classroom_administrator",
            is_first_login=False,
            organization=self.org1,
        )
        self.student_user = Student.objects.create_user(
            email="student@example.com",
            username="student",
            password="pass",
            role="student",
            organization=self.org1,
            is_first_login=False,
        )
        self.teacher_user = Teacher.objects.create_user(
            email="teacher@example.com",
            username="teacher",
            password="pass",
            role="teacher",
            is_first_login=False,
            organization=self.org1,
        )

        # --- 権限付与 ---
        self.org1.administrators.add(self.org_admin)
        self.classroom1.administrators.add(self.class_admin)

        # --- 生徒 ---
        self.student_in_class1 = Student.objects.create(
            username="s1",
            role="student",
            organization=self.org1,
            grade=1,
        )
        self.student_in_class1.classrooms.add(self.classroom1)

        self.student_in_class1_grade2 = Student.objects.create(
            username="s5",
            role="student",
            organization=self.org1,
            grade=2,
        )
        self.student_in_class1_grade2.classrooms.add(self.classroom1)

        self.student_in_class2 = Student.objects.create(
            username="s2",
            role="student",
            organization=self.org1,
            grade=2,
        )
        self.student_in_class2.classrooms.add(self.classroom2)

        self.student_other_org = Student.objects.create(
            username="s3",
            role="student",
            organization=self.org2,
            grade=3,
        )
        self.student_other_org.classrooms.add(self.classroom_other_org)

        self.inactive_student = Student.objects.create(
            username="s4",
            role="student",
            organization=self.org1,
            grade=1,
            is_active=False,
        )
        self.inactive_student.classrooms.add(self.classroom1)

        self.url_to_classroom1 = reverse(
            "organization_admin:classroom_detail",
            kwargs={"pk": self.classroom1.pk},
        )

        self.url_to_classroom2 = reverse(
            "organization_admin:classroom_detail",
            kwargs={"pk": self.classroom2.pk},
        )

        self.url_to_other_org_classroom = reverse(
            "organization_admin:classroom_detail",
            kwargs={"pk": self.classroom_other_org.pk},
        )

    # -------------------------
    # ログイン用関数
    # -------------------------
    def login_as_org_admin(self):
        ok = self.client.login(email="org_admin@example.com", password="pass")
        self.assertTrue(ok)
    
    def login_as_class_admin(self):
        ok = self.client.login(email="class_admin@example.com", password="pass")
        self.assertTrue(ok)
    
    def login_as_student_user(self):
        ok = self.client.login(email="student@example.com", password="pass")
        self.assertTrue(ok)
    
    def login_as_teacher_user(self):
        ok = self.client.login(email="teacher@example.com", password="pass")
        self.assertTrue(ok)

    # -------------------------
    # アクセス制御
    # -------------------------

    def test_org_admin_can_access(self):
        """
        組織管理者はアクセス可能
        """
        self.login_as_org_admin()
        response = self.client.get(self.url_to_classroom1)
        self.assertEqual(response.status_code, 200)
    
    def test_org_admin_can_access_other_classroom(self):
        """
        組織管理者は自身の組織であれば、異なる教室にもアクセス可能
        """
        self.login_as_org_admin()
        response = self.client.get(self.url_to_classroom2)
        self.assertEqual(response.status_code, 200)

    def test_org_admin_cannot_access_other_org_classroom(self):
        """
        組織管理者は他の組織の教室にはアクセス不可能
        """
        self.login_as_org_admin()
        response = self.client.get(self.url_to_other_org_classroom)
        self.assertEqual(response.status_code, 403)

    def test_class_admin_can_access(self):
        """
        教室管理者は自身の教室にアクセス可能
        """
        self.login_as_class_admin()
        response = self.client.get(self.url_to_classroom1)
        self.assertEqual(response.status_code, 200)
        
    def test_class_admin_cannot_access_other_classroom(self):
        """
        教室管理者は自身が管理していない教室にはアクセス不可
        """
        self.login_as_class_admin()
        response = self.client.get(self.url_to_classroom2)
        self.assertEqual(response.status_code, 403)

    def test_class_admin_cannot_access_other_org_classroom(self):
        """
        組織管理者は他の組織の教室にアクセス不可能
        """
        self.login_as_class_admin()
        response = self.client.get(self.url_to_other_org_classroom)
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_access(self):
        """
        生徒は一律アクセス不可
        """
        self.login_as_student_user()
        response = self.client.get(self.url_to_classroom1)
        self.assertEqual(response.status_code, 403)
        response = self.client.get(self.url_to_classroom2)
        self.assertEqual(response.status_code, 403)
        response = self.client.get(self.url_to_other_org_classroom)
        self.assertEqual(response.status_code, 403)

    def test_teacher_cannot_access(self):
        """
        講師は一律アクセス不可
        """
        self.login_as_teacher_user()
        response = self.client.get(self.url_to_classroom1)
        self.assertEqual(response.status_code, 403)
        response = self.client.get(self.url_to_classroom2)
        self.assertEqual(response.status_code, 403)
        response = self.client.get(self.url_to_other_org_classroom)
        self.assertEqual(response.status_code, 403)

    # -------------------------
    # 表示内容（組織管理者）
    # -------------------------

    def test_org_admin_sees_only_target_class_students(self):
        """
        組織管理者は、閲覧している教室の生徒を取得可能だが、他の教室の生徒は含まれない
        """
        self.login_as_org_admin()
        response = self.client.get(self.url_to_classroom1)

        grouped = response.context["grouped_students"]
        students = sum(grouped.values(), [])

        self.assertIn(self.student_in_class1, students)
        self.assertNotIn(self.student_in_class2, students)

    # -------------------------
    # 表示内容（教室管理者）
    # -------------------------

    def test_class_admin_sees_only_own_class_students(self):
        """
        教室管理者は自身のクラスの生徒しか見ることはできない。
        """
        self.login_as_class_admin()
        response = self.client.get(self.url_to_classroom1)

        grouped = response.context["grouped_students"]
        students = sum(grouped.values(), [])

        self.assertIn(self.student_in_class1, students)
        self.assertNotIn(self.student_in_class2, students)

    # -------------------------
    # inactive制御
    # -------------------------

    def test_inactive_students_not_displayed(self):
        """
        非アクティブ生徒は表示されない
        """
        self.login_as_org_admin()
        response = self.client.get(self.url_to_classroom1)

        grouped = response.context["grouped_students"]
        students = sum(grouped.values(), [])

        self.assertNotIn(self.inactive_student, students)

    # -------------------------
    # grouping確認
    # -------------------------
    def test_only_students_in_target_classroom_are_displayed(self):
        """
        対象教室に所属する生徒だけが表示され、他教室の生徒は表示されない
        """
        self.login_as_org_admin()
        response = self.client.get(self.url_to_classroom1)

        grouped = response.context["grouped_students"]
        displayed_students = sum(grouped.values(), [])

        self.assertIn(self.student_in_class1, displayed_students)
        self.assertNotIn(self.student_in_class2, displayed_students)
        self.assertNotIn(self.student_other_org, displayed_students)

    def test_students_in_target_classroom_are_grouped_by_grade(self):
        """
        対象教室に所属する生徒が、学年ごとに正しくグループ化される
        """
        self.login_as_org_admin()
        response = self.client.get(self.url_to_classroom1)

        grouped = response.context["grouped_students"]

        grade1 = self.student_in_class1.get_grade_display()
        grade2 = self.student_in_class1_grade2.get_grade_display()

        self.assertIn(grade1, grouped)
        self.assertIn(grade2, grouped)

        self.assertIn(self.student_in_class1, grouped[grade1])
        self.assertIn(self.student_in_class1_grade2, grouped[grade2])

        self.assertNotIn(self.student_in_class1_grade2, grouped[grade1])
        self.assertNotIn(self.student_in_class1, grouped[grade2])
