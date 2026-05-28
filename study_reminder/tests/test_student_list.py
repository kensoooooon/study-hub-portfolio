from datetime import time

from django.test import RequestFactory, TestCase

from accounts.models import (
    Organization,
    Classroom,
    OrganizationAdministrator,
    ClassroomAdministrator,
    Teacher,
    Student,
)
from study_reminder.models import StudyReminder
from study_reminder.views import StudentListView


class StudentListViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.org1 = Organization.objects.create(name="Org1")
        self.org2 = Organization.objects.create(name="Org2")

        self.classroom1 = Classroom.objects.create(name="Classroom1", organization=self.org1)
        self.classroom2 = Classroom.objects.create(name="Classroom2", organization=self.org2)

        self.org_admin = OrganizationAdministrator.objects.create_user(
            email="orgadmin@example.com",
            password="testpass123",
            username="orgadmin",
        )
        self.org_admin.organizations.add(self.org1)

        self.classroom_admin = ClassroomAdministrator.objects.create_user(
            email="classadmin@example.com",
            password="testpass123",
            username="classadmin",
            organization=self.org1,
        )
        self.classroom_admin.classrooms.add(self.classroom1)

        self.teacher = Teacher.objects.create_user(
            email="teacher@example.com",
            password="testpass123",
            username="teacher",
            organization=self.org1,
        )
        self.teacher.classrooms.add(self.classroom1)

        self.active_student = Student.objects.create_user(
            email="active@example.com",
            password="testpass123",
            username="active_student",
            organization=self.org1,
            is_active=True,
            line_user_id="line-001",
        )
        self.active_student.classrooms.add(self.classroom1)
        self.active_student.teachers.add(self.teacher)

        self.inactive_student = Student.objects.create_user(
            email="inactive@example.com",
            password="testpass123",
            username="inactive_student",
            organization=self.org1,
            is_active=False,
            line_user_id="line-002",
        )
        self.inactive_student.classrooms.add(self.classroom1)
        self.inactive_student.teachers.add(self.teacher)

        self.other_org_student = Student.objects.create_user(
            email="other@example.com",
            password="testpass123",
            username="other_org_student",
            organization=self.org2,
            is_active=True,
            line_user_id="line-003",
        )
        self.other_org_student.classrooms.add(self.classroom2)

        StudyReminder.objects.create(
            student=self.active_student,
            day_of_week="monday",
            time_of_day=time(9, 0),
            is_active=True,
            custom_message="hello",
        )
        StudyReminder.objects.create(
            student=self.inactive_student,
            day_of_week="monday",
            time_of_day=time(9, 15),
            is_active=True,
            custom_message="hidden",
        )

    def _get_queryset(self, user):
        request = self.factory.get("/study_reminder/students/")
        request.user = user

        view = StudentListView()
        view.setup(request)
        return view.get_queryset()

    def test_org_admin_sees_only_own_active_students(self):
        """
        組織管理者は自身の組織に所属するアクティブな生徒のみ閲覧可能
        """
        qs = self._get_queryset(self.org_admin)

        self.assertIn(self.active_student, qs)
        self.assertNotIn(self.inactive_student, qs)
        self.assertNotIn(self.other_org_student, qs)

    def test_classroom_admin_sees_only_classroom_active_students(self):
        """
        教室管理者は自身の管理教室に所属するアクティブな生徒のみ閲覧可能
        """
        qs = self._get_queryset(self.classroom_admin)

        self.assertIn(self.active_student, qs)
        self.assertNotIn(self.inactive_student, qs)
        self.assertNotIn(self.other_org_student, qs)

    def test_teacher_sees_only_assigned_active_students(self):
        """
        講師は割り当てられたアクティブな生徒のみ閲覧可能
        """
        qs = self._get_queryset(self.teacher)

        self.assertIn(self.active_student, qs)
        self.assertNotIn(self.inactive_student, qs)
        self.assertNotIn(self.other_org_student, qs)

    def test_prefetched_reminders_exclude_inactive_student_side(self):
        """
        prefetchされたリマインダーには非アクティブな生徒のものが含まれない
        """
        qs = self._get_queryset(self.org_admin)
        student = qs.get(pk=self.active_student.pk)

        reminders = list(student.study_reminders.all())
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0].student, self.active_student)
