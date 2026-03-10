from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from accounts.models import Student, Teacher, ClassroomAdministrator, OrganizationAdministrator


class EmailNormalizationTests(TestCase):
    def test_baseuser_create_user_normalizes_email_to_lower_and_strips(self):
        User = get_user_model()
        u = User.objects.create_user(
            email="  SampleIncludingUpperCase@EXAMPLE.com  ",
            password="pass123",
            role="teacher",
            username="T",
        )
        self.assertEqual(u.email, "sampleincludinguppercase@example.com")

    def test_subclass_create_user_normalizes_email(self):
        t = Teacher.objects.create_user(
            email="TeAcher@Example.COM",
            password="pass123",
            username="Teacher",
        )
        self.assertEqual(t.email, "teacher@example.com")

        ca = ClassroomAdministrator.objects.create_user(
            email="CA@Example.COM",
            password="pass123",
            username="CA",
        )
        self.assertEqual(ca.email, "ca@example.com")

        oa = OrganizationAdministrator.objects.create_user(
            email="OA@Example.COM",
            password="pass123",
            username="OA",
        )
        self.assertEqual(oa.email, "oa@example.com")

    def test_student_email_can_be_none_and_stays_none(self):
        s = Student.objects.create_user(
            email=None,
            password="pass123",
            username="Student",
        )
        self.assertIsNone(s.email)

    def test_email_case_collision_is_prevented(self):
        User = get_user_model()
        User.objects.create_user(
            email="Foo@Example.com",
            password="pass123",
            role="teacher",
            username="U1",
        )
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                email="foo@example.com",
                password="pass123",
                role="teacher",
                username="U2",
            )
