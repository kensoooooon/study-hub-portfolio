import json
from datetime import date, datetime, time
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from accounts.models import Organization, Student
from study_reminder.models import StudyReminder
from study_reminder.views import process_reminders


def unwrap_view(func):
    """
    decorator を外して元の view 関数に辿る。
    __wrapped__ が無くなるまで剥がす。
    """
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func


class ProcessRemindersViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.org = Organization.objects.create(name="Org1")

        self.student = Student.objects.create_user(
            email="student@example.com",
            password="testpass123",
            username="student",
            organization=self.org,
            is_active=True,
            line_user_id="line-001",
        )
        self.inactive_student = Student.objects.create_user(
            email="inactive@example.com",
            password="testpass123",
            username="inactive_student",
            organization=self.org,
            is_active=False,
            line_user_id="line-002",
        )

    def _create_reminder(self, *, student, hh=9, mm=0, is_active=True, last_notified=None):
        return StudyReminder.objects.create(
            student=student,
            day_of_week="monday",
            time_of_day=time(hh, mm),
            is_active=is_active,
            last_notified=last_notified,
            custom_message="hello",
        )

    @override_settings(ENV="local")
    def test_get_returns_405(self):
        """
        GETメソッドはきちんと弾く
        """
        request = self.factory.get("/study_reminder/process/")
        response = unwrap_view(process_reminders)(request)

        self.assertEqual(response.status_code, 405)

    @override_settings(ENV="local")
    @patch("study_reminder.views.localtime")
    def test_successful_send_updates_last_notified_and_count(self, mock_localtime):
        """
        送信が成功したときに、最終送信日とカウントがアップデートされる
        """
        mock_localtime.return_value = timezone.make_aware(datetime(2026, 4, 13, 9, 3, 0))

        reminder = self._create_reminder(student=self.student, hh=9, mm=0, is_active=True)

        request = self.factory.post("/study_reminder/process/")
        with patch.object(StudyReminder, "send_notification", return_value=True) as mock_send:
            response = unwrap_view(process_reminders)(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["processed_reminders"], 1)

        reminder.refresh_from_db()
        self.assertEqual(reminder.last_notified, date(2026, 4, 13))
        mock_send.assert_called_once()

    @override_settings(ENV="local")
    @patch("study_reminder.views.localtime")
    def test_failed_send_does_not_update_last_notified(self, mock_localtime):
        """
        送信が失敗したときは、最終送信日がアップデートされない
        """
        mock_localtime.return_value = timezone.make_aware(datetime(2026, 4, 13, 9, 3, 0))

        reminder = self._create_reminder(student=self.student, hh=9, mm=0, is_active=True)

        request = self.factory.post("/study_reminder/process/")
        with patch.object(StudyReminder, "send_notification", return_value=False):
            response = unwrap_view(process_reminders)(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["processed_reminders"], 0)

        reminder.refresh_from_db()
        self.assertIsNone(reminder.last_notified)

    @override_settings(ENV="local")
    @patch("study_reminder.views.localtime")
    def test_inactive_student_reminder_is_not_processed(self, mock_localtime):
        """
        非アクティブ化された生徒はリマインダーを処理されない
        """
        mock_localtime.return_value = timezone.make_aware(datetime(2026, 4, 13, 9, 3, 0))

        self._create_reminder(student=self.inactive_student, hh=9, mm=0, is_active=True)

        request = self.factory.post("/study_reminder/process/")
        with patch.object(StudyReminder, "send_notification", return_value=True) as mock_send:
            response = unwrap_view(process_reminders)(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["processed_reminders"], 0)
        mock_send.assert_not_called()

    @override_settings(ENV="local")
    @patch("study_reminder.views.localtime")
    def test_already_notified_today_is_not_processed(self, mock_localtime):
        """
        既に送信済みのリマインダーは再送信されない
        """
        mock_localtime.return_value = timezone.make_aware(datetime(2026, 4, 13, 9, 3, 0))

        self._create_reminder(
            student=self.student,
            hh=9,
            mm=0,
            is_active=True,
            last_notified=date(2026, 4, 13),
        )

        request = self.factory.post("/study_reminder/process/")
        with patch.object(StudyReminder, "send_notification", return_value=True) as mock_send:
            response = unwrap_view(process_reminders)(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["processed_reminders"], 0)
        mock_send.assert_not_called()

    @override_settings(ENV="prod")
    def test_invalid_user_agent_returns_403_in_non_local(self):
        """
        local以外の環境では、不正なUser-Agentのリクエストを403で拒否する
        """
        request = self.factory.post(
            "/study_reminder/process/",
            HTTP_USER_AGENT="invalid-agent",
        )
        response = unwrap_view(process_reminders)(request)

        self.assertEqual(response.status_code, 403)


    @override_settings(ENV="prod")
    def test_valid_user_agent_returns_200_in_non_local(self):
        """
        Google-Cloud-Schedulerはアクセス可能
        """
        request = self.factory.post(
            "/study_reminder/process/",
            HTTP_USER_AGENT="Google-Cloud-Scheduler",
        )
        response = unwrap_view(process_reminders)(request)

        self.assertEqual(response.status_code, 200)
