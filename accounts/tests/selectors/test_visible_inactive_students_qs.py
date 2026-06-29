from django.test import TestCase
from django.contrib.auth.models import AnonymousUser
from unittest.mock import Mock


from accounts.models import (
    Student,
    Teacher,
    ClassroomAdministrator,
    OrganizationAdministrator,
    Classroom,
    Organization
)
from accounts.selectors import visible_inactive_students_qs


class VisibleInactiveStudentQsTest(TestCase):
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
            organization=cls.org1
        )
        cls.class1_1_admin.classrooms.add(cls.class1_1)
        cls.class1_1_teacher = Teacher.objects.create_user(
            username="class1_1_teacher",
            email="class1_1_teacher@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.class1_1_teacher.classrooms.add(cls.class1_1)

        cls.class1_1_active_student = Student.objects.create_user(
            username="class1_1_active_student",
            email="class1_1_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_1_active_student"
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

        cls.class1_1_inactive_student_without_teacher = Student.objects.create_user(
            username="class1_1_inactive_student_without_teacher",
            email="class1_1_inactive_student_without_teacher@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_1_inactive_student_without_teacher"
        )
        cls.class1_1_inactive_student_without_teacher.classrooms.add(cls.class1_1)

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
        cls.class1_2_inactive_student = Student.objects.create_user(
            username="class1_2_inactive_student",
            email="class1_2_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_2_inactive_student"
        )
        cls.class1_2_inactive_student.classrooms.add(cls.class1_2)

        cls.class1_not_active_student = Student.objects.create_user(
            username="class1_not_active_student",
            email="class1_not_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_not_active_student"
        )
        cls.class1_not_inactive_student = Student.objects.create_user(
            username="class1_not_inactive_student",
            email="class1_not_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_not_inactive_student"
        )


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

    # 正常系テスト
    def test_anonymous_user_cannot_get_anything(self):
        """
        未ログインユーザーは何も得られない
        """
        user = AnonymousUser()
        qs = visible_inactive_students_qs(user)
        self.assertEqual(qs.count(), 0)
    
    def test_student_cannot_get_anything(self):
        """
        生徒は何も得られない
        """
        students = [
            self.class1_1_active_student,
            self.class1_1_inactive_student,
            self.class1_1_inactive_student_without_teacher,
            self.class1_2_active_student,
            self.class1_2_inactive_student,
            self.class2_active_student,
            self.class2_inactive_student,
            self.class1_not_active_student,
            self.class1_not_inactive_student,
            ]
        for student in students:
            qs = visible_inactive_students_qs(student)
            self.assertEqual(qs.count(), 0)
        
    def test_teacher_can_get_only_assigned_inactive_student(self):
        """
        講師は自身の担当している非アクティブな生徒のみ見える
        """
        qs = visible_inactive_students_qs(self.class1_1_teacher)
        self.assertNotIn(self.class1_1_active_student, qs)
        self.assertIn(self.class1_1_inactive_student, qs)
        self.assertNotIn(self.class1_1_inactive_student_without_teacher, qs)
        self.assertNotIn(self.class1_2_active_student, qs)
        self.assertNotIn(self.class1_2_inactive_student, qs)
        self.assertNotIn(self.class1_not_active_student, qs)
        self.assertNotIn(self.class1_not_inactive_student, qs)
        self.assertNotIn(self.class2_active_student, qs)
        self.assertNotIn(self.class2_inactive_student, qs)
        self.assertEqual(qs.count(), 1)
    
    def test_class_admin_can_get_only_assigned_inactive_student(self):
        """
        教室管理者は自身の教室に所属している非アクティブな生徒のみ見える
        """
        qs = visible_inactive_students_qs(self.class1_1_admin)
        self.assertNotIn(self.class1_1_active_student, qs)
        self.assertIn(self.class1_1_inactive_student, qs)
        self.assertIn(self.class1_1_inactive_student_without_teacher, qs)
        self.assertNotIn(self.class1_2_active_student, qs)
        self.assertNotIn(self.class1_2_inactive_student, qs)
        self.assertNotIn(self.class1_not_active_student, qs)
        self.assertNotIn(self.class1_not_inactive_student, qs)
        self.assertNotIn(self.class2_active_student, qs)
        self.assertNotIn(self.class2_inactive_student, qs)
        self.assertEqual(qs.count(), 2)
    
    def test_org_admin_can_get_only_assigned_inactive_student(self):
        """
        組織管理者は、自身の組織に所属している非アクティブな生徒のみ見える
        """
        qs = visible_inactive_students_qs(self.org1_admin)
        self.assertNotIn(self.class1_1_active_student, qs)
        self.assertIn(self.class1_1_inactive_student, qs)
        self.assertIn(self.class1_1_inactive_student_without_teacher, qs)
        self.assertNotIn(self.class1_2_active_student, qs)
        self.assertIn(self.class1_2_inactive_student, qs)
        self.assertNotIn(self.class1_not_active_student, qs)
        self.assertIn(self.class1_not_inactive_student, qs)
        self.assertNotIn(self.class2_active_student, qs)
        self.assertNotIn(self.class2_inactive_student, qs)
        self.assertEqual(qs.count(), 4)

    def test_user_without_role_object_cannot_get_anything(self):
        """
        ロールオブジェクトが取得できない場合は何も見られない
        """
        self.org1_admin.get_role_object = Mock(return_value=None)
        qs = visible_inactive_students_qs(self.org1_admin)
        self.assertEqual(qs.count(), 0)
