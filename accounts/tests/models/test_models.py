from django.test import TestCase
from accounts.models import Student, Teacher, ClassroomAdministrator, OrganizationAdministrator

class StudentModelTest(TestCase):
    def test_create_student_with_email(self):
        student = Student.objects.create_user(email="student@example.com", password="password123", username="Test Student")
        self.assertEqual(student.email, "student@example.com")
        self.assertTrue(student.check_password("password123"))
        self.assertEqual(student.role, "student")
        self.assertEqual(student.username, "Test Student")

    def test_create_student_without_email(self):
        student = Student.objects.create_user(username="No Email Student", password="password123")
        self.assertIsNone(student.email)
        self.assertEqual(student.username, "No Email Student")


class TeacherModelTest(TestCase):
    def test_create_teacher(self):
        teacher = Teacher.objects.create_user(email="teacher@example.com", password="password123", username="Test Teacher")
        self.assertEqual(teacher.email, "teacher@example.com")
        self.assertTrue(teacher.check_password("password123"))
        self.assertEqual(teacher.role, "teacher")
        self.assertEqual(teacher.username, "Test Teacher")


class ClassroomAdministratorModelTest(TestCase):
    def test_create_classroom_administrator(self):
        admin = ClassroomAdministrator.objects.create_user(
            email="classroom_admin@example.com",
            password="password123",
            username="Classroom Admin"
        )
        self.assertEqual(admin.email, "classroom_admin@example.com")
        self.assertTrue(admin.check_password("password123"))
        self.assertEqual(admin.role, "classroom_administrator")
        self.assertEqual(admin.username, "Classroom Admin")


class OrganizationAdministratorModelTest(TestCase):
    def test_create_organization_administrator(self):
        admin = OrganizationAdministrator.objects.create_user(
            email="org_admin@example.com",
            password="password123",
            username="Organization Admin"
        )
        self.assertEqual(admin.email, "org_admin@example.com")
        self.assertTrue(admin.check_password("password123"))
        self.assertEqual(admin.role, "organization_administrator")
        self.assertEqual(admin.username, "Organization Admin")
