from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from accounts.models import (
    Student,
    Teacher,
    ClassroomAdministrator,
    OrganizationAdministrator,
    Organization,
    Classroom,
)
from vocab_trainer.models import Textbook


class StudentViewsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Org 1")
        cls.classroom = Classroom.objects.create(name="Classroom 1", organization=cls.org)

        cls.textbook = Textbook.objects.create(
            name="Test Book",
            publisher="Test Publisher",
            grade=1,
        )

        cls.student = Student.objects.create_user(
            username="student1",
            email="student1@example.com",
            password="pass123456",
            organization=cls.org,
            textbook=cls.textbook,
        )

        cls.student.classrooms.add(cls.classroom)

        cls.inactive_student = Student.objects.create_user(
            username="inactive_student",
            email="inactive_student@example.com",
            password="pass123456",
            organization=cls.org,
            is_active=False,
        )
        cls.inactive_student.classrooms.add(cls.classroom)

        cls.teacher = Teacher.objects.create_user(
            username="teacher1",
            email="teacher1@example.com",
            password="pass123456",
            organization=cls.org,
        )
        cls.teacher.classrooms.add(cls.classroom)

        cls.classroom_admin = ClassroomAdministrator.objects.create_user(
            username="classroom_admin1",
            email="classroom_admin1@example.com",
            password="pass123456",
            organization=cls.org,
        )
        cls.classroom_admin.classrooms.add(cls.classroom)

        cls.org_admin = OrganizationAdministrator.objects.create_user(
            username="org_admin1",
            email="org_admin1@example.com",
            password="pass123456",
        )
        cls.org_admin.organizations.add(cls.org)


    def test_student_home_student_can_access(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/student/home.html")
        self.assertEqual(response.context["student"].pk, self.student.pk)

    def test_student_home_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts_auth:login"), response.url)

    def test_student_home_teacher_cannot_access(self):
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts_auth:login"))

    def test_student_home_org_admin_cannot_access(self):
        self.client.force_login(self.org_admin)

        response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts_auth:login"))

    def test_student_home_classroom_admin_cannot_access(self):
        self.client.force_login(self.classroom_admin)

        response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts_auth:login"))

    def test_student_home_has_vocab_progress_is_false_when_no_progress(self):
        """vocab進捗がない生徒では has_vocab_progress が False としてコンテキストに渡る"""
        self.client.force_login(self.student)
        response = self.client.get(reverse("student:home"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["has_vocab_progress"])

    @patch("accounts.views.student_views.has_vocab_progress", return_value=True)
    def test_student_home_has_vocab_progress_is_true_with_progress(self, _):
        """vocab進捗がある生徒では has_vocab_progress が True としてコンテキストに渡る"""
        self.client.force_login(self.student)
        response = self.client.get(reverse("student:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["has_vocab_progress"])

    def test_student_home_inactive_student_cannot_access(self):
        self.client.force_login(self.inactive_student)

        response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            f"{reverse('accounts_auth:login')}?next={reverse('student:home')}"
        )

    def test_study_english_history_student_can_access(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("student:english_history"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/student/english_history.html")
        self.assertEqual(response.context["student"].pk, self.student.pk)
        self.assertIn("word_progresses", response.context)

    def test_study_english_history_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("student:english_history"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts_auth:login"), response.url)

    def test_study_english_history_teacher_cannot_access(self):
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("student:english_history"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts_auth:login"))


    def test_study_english_history_inactive_student_cannot_access(self):
        self.client.force_login(self.inactive_student)

        response = self.client.get(reverse("student:english_history"))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            f"{reverse('accounts_auth:login')}?next={reverse('student:english_history')}"
        )


    def test_study_chemical_history_student_can_access(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("student:chemical_history"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/student/chemical_history.html")
        self.assertEqual(response.context["student"].pk, self.student.pk)
        self.assertIn("chemical_progresses", response.context)

    def test_study_chemical_history_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("student:chemical_history"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts_auth:login"), response.url)

    def test_study_chemical_history_teacher_cannot_access(self):
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("student:chemical_history"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts_auth:login"))

    def test_study_chemical_history_inactive_student_cannot_access(self):
        self.client.force_login(self.inactive_student)

        response = self.client.get(reverse("student:chemical_history"))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            f"{reverse('accounts_auth:login')}?next={reverse('student:chemical_history')}"
        )

    def test_student_home_hides_read_and_listening_links_without_vocab_progress(self):
        """
        教科書は設定済みだがvocab進捗がない場合、
        read/listening導線を表示せず、英単語学習への案内を表示する
        """
        self.client.force_login(self.student)

        response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "長文・リスニング学習を利用するには、まず英単語学習を進めてください。")

        self.assertNotContains(response, reverse("read_trainer:quiz_type_select_for_student"))
        self.assertNotContains(response, reverse("read_trainer:eiken_quiz_type_select_for_student"))
        self.assertNotContains(response, reverse("listening_trainer:quiz_type_select_for_student"))
        self.assertNotContains(response, reverse("listening_trainer:eiken_quiz_type_select_for_student"))

        self.assertContains(response, reverse("vocab_trainer:quiz_type_select_for_student"))
        self.assertContains(response, reverse("math_trainer:index"))

    @patch("accounts.views.student_views.has_vocab_progress", return_value=True)
    def test_student_home_shows_read_and_listening_links_with_vocab_progress(self, _):
        """
        教科書が設定済みでvocab進捗がある場合、
        read/listening導線を表示する
        """
        self.client.force_login(self.student)

        response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("read_trainer:quiz_type_select_for_student"))
        self.assertContains(response, reverse("read_trainer:eiken_quiz_type_select_for_student"))
        self.assertContains(response, reverse("listening_trainer:quiz_type_select_for_student"))
        self.assertContains(response, reverse("listening_trainer:eiken_quiz_type_select_for_student"))