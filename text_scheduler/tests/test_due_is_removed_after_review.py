import datetime
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Organization, Classroom, Teacher, Student
from text_scheduler.models import LearningMaterial, StudentUnitProgress, StudyLog
from text_scheduler.services import apply_study_log


class TestDueIsRemovedAfterReview(TestCase):

    def setUp(self):
        org = Organization.objects.create(name="Org")
        cls = Classroom.objects.create(name="Cls-1", organization=org)

        self.teacher = Teacher.objects.create_user(
            email="teacher@example.com",
            password="pass",
            role="teacher",
            is_first_login=False,
            organization=org,
        )
        self.teacher.classrooms.add(cls)

        self.student = Student.objects.create_user(
            username="stu",
            role="student",
            organization=org,
        )
        self.student.classrooms.add(cls)
        self.student.teachers.add(self.teacher)

        self.material = LearningMaterial.objects.create(
            target_student=self.student,
            created_by=self.teacher,
            title="テスト教材",
            unit_label="番",
            start_number=100,
            end_number=200,
            required_reviews=2,
            estimated_minutes_per_unit=5,
            start_date=timezone.localdate(),
            goal_date=timezone.localdate() + datetime.timedelta(days=30),
            buffer_weekdays=[],
        )

    def test_due_is_removed_after_review(self):
        self.client.force_login(self.teacher)

        StudentUnitProgress.objects.create(
            student=self.student,
            material=self.material,
            number=145,
            next_due_at=timezone.now() - datetime.timedelta(days=1),
            repetition_count=1,
        )

        url = reverse("text_scheduler:material_list")
        resp1 = self.client.get(url + f"?student_id={self.student.pk}")
        self.assertEqual(resp1.status_code, 200)
        self.assertIn("145", resp1.content.decode())

        log = StudyLog.objects.create(
            student=self.student,
            material=self.material,
            number=145,
            kind="review",
            quality=4,
        )
        apply_study_log(log)

        resp2 = self.client.get(url + f"?student_id={self.student.pk}")
        self.assertEqual(resp2.status_code, 200)
        self.assertNotIn("145", resp2.content.decode())

        self.assertContains(resp1, "番145")
        self.assertNotContains(resp2, "番145")