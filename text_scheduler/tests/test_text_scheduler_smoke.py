import datetime as dt
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Organization, Classroom, Teacher, Student
from text_scheduler.models import LearningMaterial


class TestCreateUpdateDeleteFlow(TestCase):

    def setUp(self):
        org = Organization.objects.create(name="OrgA")
        cls = Classroom.objects.create(name="A-1", organization=org)

        self.teacher = Teacher.objects.create_user(
            email="t@example.com",
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

        self.client.force_login(self.teacher)

    def test_create_update_delete_flow(self):
        url = reverse("text_scheduler:material_create", kwargs={"student_id": self.student.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        today = timezone.now().date()
        payload = {
            "title": "Unit 1",
            "unit_label": "page",
            "start_number": 1,
            "end_number": 3,
            "required_reviews": 2,
            "estimated_minutes_per_unit": 10,
            "daily_minutes_budget": 45,
            "start_date": today.isoformat(),
            "goal_date": (today + dt.timedelta(days=30)).isoformat(),
            "buffer_weekdays": ["0", "2", "4"],
            "is_archived": False,
            "student_id": str(self.student.pk),
        }
        resp = self.client.post(url, data=payload)
        self.assertEqual(resp.status_code, 302)
        obj = LearningMaterial.objects.get(title="Unit 1")
        self.assertEqual(obj.created_by_id, self.teacher.pk)
        self.assertEqual(obj.target_student_id, self.student.pk)

        edit = reverse("text_scheduler:material_edit", kwargs={"pk": obj.pk})
        resp = self.client.get(edit)
        self.assertEqual(resp.status_code, 200)
        payload["title"] = "Unit 1 (rev)"
        resp = self.client.post(edit, data=payload, follow=True)
        self.assertEqual(resp.status_code, 200)
        obj.refresh_from_db()
        self.assertEqual(obj.title, "Unit 1 (rev)")

        delete = reverse("text_scheduler:material_delete", kwargs={"pk": obj.pk})
        resp = self.client.post(
            delete,
            data={"student_id": str(self.student.pk)},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(LearningMaterial.objects.filter(pk=obj.pk).exists())


class TestAccessControlDeniesOtherTeacher(TestCase):

    def setUp(self):
        org = Organization.objects.create(name="OrgB")
        cls = Classroom.objects.create(name="B-1", organization=org)

        t1 = Teacher.objects.create_user(
            email="t1@example.com",
            password="pass",
            role="teacher",
            is_first_login=False,
            organization=org,
        )
        t1.classrooms.add(cls)

        self.t2 = Teacher.objects.create_user(
            email="t2@example.com",
            password="pass",
            role="teacher",
            is_first_login=False,
            organization=org,
        )
        self.t2.classrooms.add(cls)

        self.stu = Student.objects.create_user(
            username="s",
            role="student",
            organization=org,
        )
        self.stu.classrooms.add(cls)
        self.stu.teachers.add(t1)

        today = timezone.now().date()
        self.lm = LearningMaterial.objects.create(
            title="x",
            unit_label="page",
            start_number=1,
            end_number=1,
            required_reviews=1,
            estimated_minutes_per_unit=5,
            daily_minutes_budget=45,
            start_date=today,
            goal_date=today + dt.timedelta(days=30),
            buffer_weekdays=[1],
            is_archived=False,
            target_student=self.stu,
            created_by=t1,
        )

        self.client.force_login(self.t2)

    def test_edit_denied(self):
        resp = self.client.get(
            reverse("text_scheduler:material_edit", kwargs={"pk": self.lm.pk})
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_denied(self):
        resp = self.client.post(
            reverse("text_scheduler:material_delete", kwargs={"pk": self.lm.pk})
        )
        self.assertEqual(resp.status_code, 404)
