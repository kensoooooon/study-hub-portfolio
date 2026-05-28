from datetime import date, time

from django.test import TestCase

from accounts.models import (
    Organization,
    Classroom,
    OrganizationAdministrator,
    ClassroomAdministrator,
    Teacher,
    Student,
)
from study_reminder.models import StudyReminder


class StudyReminderQuerySetTest(TestCase):
    def setUp(self):
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

        self.student_active = Student.objects.create_user(
            email="student1@example.com",
            password="testpass123",
            username="student_active",
            organization=self.org1,
            is_active=True,
            line_user_id="line-001",
        )
        self.student_active.classrooms.add(self.classroom1)
        self.student_active.teachers.add(self.teacher)

        self.student_inactive = Student.objects.create_user(
            email="student2@example.com",
            password="testpass123",
            username="student_inactive",
            organization=self.org1,
            is_active=False,
            line_user_id="line-002",
        )
        self.student_inactive.classrooms.add(self.classroom1)
        self.student_inactive.teachers.add(self.teacher)

        self.student_other_org = Student.objects.create_user(
            email="student3@example.com",
            password="testpass123",
            username="student_other_org",
            organization=self.org2,
            is_active=True,
            line_user_id="line-003",
        )
        self.student_other_org.classrooms.add(self.classroom2)

    def _create_reminder(
        self,
        *,
        student,
        day_of_week="monday",
        hh=9,
        mm=0,
        is_active=True,
        last_notified=None,
        custom_message="msg",
    ):
        return StudyReminder.objects.create(
            student=student,
            day_of_week=day_of_week,
            time_of_day=time(hh, mm),
            is_active=is_active,
            last_notified=last_notified,
            custom_message=custom_message,
        )

    def test_active_returns_only_active_reminders(self):
        """
        activeメソッドはアクティブなリマインダー以外は返さないか
        """
        active_reminder = self._create_reminder(student=self.student_active, is_active=True)
        inactive_reminder = self._create_reminder(student=self.student_active, is_active=False, hh=9, mm=15)

        qs = StudyReminder.objects.active()

        self.assertIn(active_reminder, qs)
        self.assertNotIn(inactive_reminder, qs)

    def test_with_active_student_excludes_inactive_students(self):
        """
        with_active_studentメソッドは無効な生徒を除外するか
        """
        visible = self._create_reminder(student=self.student_active)
        hidden = self._create_reminder(student=self.student_inactive, hh=9, mm=15)

        qs = StudyReminder.objects.with_active_student()

        self.assertIn(visible, qs)
        self.assertNotIn(hidden, qs)

    def test_notifiable_in_slot_returns_only_matching_reminders(self):
        """
        notifiable_in_slotメソッドは、条件にマッチするもののみ返すか
        """
        target = self._create_reminder(
            student=self.student_active,
            day_of_week="monday",
            hh=9,
            mm=0,
            is_active=True,
            last_notified=None,
        )
        self._create_reminder(  # 別スロット
            student=self.student_active,
            day_of_week="monday",
            hh=9,
            mm=15,
            is_active=True,
        )
        self._create_reminder(  # 別曜日
            student=self.student_active,
            day_of_week="tuesday",
            hh=9,
            mm=0,
            is_active=True,
        )
        self._create_reminder(  # reminder inactive
            student=self.student_active,
            day_of_week="monday",
            hh=9,
            mm=0,
            is_active=False,
        )
        self._create_reminder(  # student inactive
            student=self.student_inactive,
            day_of_week="monday",
            hh=9,
            mm=0,
            is_active=True,
        )
        self._create_reminder(  # 今日すでに通知済み
            student=self.student_active,
            day_of_week="monday",
            hh=9,
            mm=0,
            is_active=True,
            last_notified=date(2026, 4, 13),
        )

        qs = StudyReminder.objects.notifiable_in_slot(
            day_of_week="monday",
            start_time=time(9, 0),
            end_time=time(9, 15),
            target_date=date(2026, 4, 13),
        )

        self.assertEqual(list(qs), [target])

    def test_filter_by_access_for_org_admin(self):
        """
        組織管理者に対するfilter_by_accessは組織の壁をきちんと守れているか
        """
        own_reminder = self._create_reminder(student=self.student_active)
        other_org_reminder = self._create_reminder(student=self.student_other_org, hh=9, mm=15)

        qs = StudyReminder.objects.filter_by_access(self.org_admin)

        self.assertIn(own_reminder, qs)
        self.assertNotIn(other_org_reminder, qs)

    def test_filter_by_access_for_classroom_admin_excludes_inactive_students(self):
        """
        教室管理者に対するfilter_by_accessは、非アクティブ化された生徒をきちんと除外し、アクティブなリマインダーのみを取得するか
        """
        active_reminder = self._create_reminder(student=self.student_active)
        inactive_student_reminder = self._create_reminder(student=self.student_inactive, hh=9, mm=15)

        qs = StudyReminder.objects.filter_by_access(self.classroom_admin)

        self.assertIn(active_reminder, qs)
        self.assertNotIn(inactive_student_reminder, qs)

    def test_filter_by_access_for_teacher(self):
        """
        講師に対するfilter_by_accessは、他組織のリマインダーを除外できるか
        """
        own_student_reminder = self._create_reminder(student=self.student_active)
        other_org_reminder = self._create_reminder(student=self.student_other_org, hh=9, mm=15)

        qs = StudyReminder.objects.filter_by_access(self.teacher)

        self.assertIn(own_student_reminder, qs)
        self.assertNotIn(other_org_reminder, qs)
