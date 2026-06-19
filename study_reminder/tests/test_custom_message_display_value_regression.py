"""
Regression tests for Issue #14: display value must not be saved to DB.

Ensures that "ChatGPTの自動メッセージ" (or any other help text) is never
persisted as custom_message via the form.  Covers:

- clean_custom_message normalises "" to None
- custom_message=None reminder: editing does not inject help text into input value
- Posting empty string saves None to DB
- Re-saving a None reminder keeps None
- Posting an actual message saves it correctly
"""
from datetime import time

from django.test import TestCase
from django.urls import reverse

from accounts.models import Classroom, Organization, Student, Teacher
from study_reminder.forms import StudyReminderEditForm
from study_reminder.models import StudyReminder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_org_teacher_student(suffix):
    org = Organization.objects.create(name=f"org_{suffix}")
    classroom = Classroom.objects.create(name=f"cls_{suffix}", organization=org)
    teacher = Teacher.objects.create_user(
        username=f"teacher_{suffix}",
        email=f"teacher_{suffix}@example.com",
        password="pass",
        organization=org,
        is_first_login=False,
    )
    teacher.classrooms.add(classroom)
    student = Student.objects.create_user(
        username=f"student_{suffix}",
        email=f"student_{suffix}@example.com",
        password="pass",
        organization=org,
        is_active=True,
        line_user_id=f"uid_{suffix}",
    )
    student.classrooms.add(classroom)
    student.teachers.add(teacher)
    return teacher, student


# ---------------------------------------------------------------------------
# Form unit tests
# ---------------------------------------------------------------------------

class CustomMessageFormNormalizationTest(TestCase):
    """clean_custom_message の正規化ロジック単体テスト。"""

    @classmethod
    def setUpTestData(cls):
        _, cls.student = _make_org_teacher_student("form_norm")
        cls.reminder = StudyReminder.objects.create(
            student=cls.student,
            day_of_week="monday",
            time_of_day=time(9, 0),
            custom_message=None,
        )

    def _form(self, custom_message):
        return StudyReminderEditForm(
            data={
                "day_of_week": "monday",
                "time_of_day": "09:00",
                "custom_message": custom_message,
                "learning_link_destination": "",
            },
            instance=self.reminder,
            student=self.student,
        )

    def test_empty_string_is_normalized_to_none(self):
        """
        空の文字列はNoneに正規化されてフォームに格納される
        """
        form = self._form("")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["custom_message"])

    def test_none_stays_none(self):
        """
        NoneはNoneのままフォームに格納される
        """
        form = self._form(None)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["custom_message"])

    def test_actual_message_is_preserved(self):
        """
        空でもNoneでもないメッセージはそのままフォームに格納される
        """
        form = self._form("頑張れ！")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["custom_message"], "頑張れ！")


# ---------------------------------------------------------------------------
# View GET: initial value must not contain help text
# ---------------------------------------------------------------------------

class CustomMessageEditViewGetTest(TestCase):
    """編集画面のGET時に表示用文言が input value に混入しないことを検証する。"""

    @classmethod
    def setUpTestData(cls):
        cls.teacher, cls.student = _make_org_teacher_student("view_get")
        cls.reminder = StudyReminder.objects.create(
            student=cls.student,
            day_of_week="monday",
            time_of_day=time(9, 0),
            custom_message=None,
        )

    def _get(self):
        self.client.force_login(self.teacher)
        return self.client.get(
            reverse("reminder_edit", kwargs={"pk": self.reminder.pk})
        )

    def test_form_initial_custom_message_is_empty_when_null(self):
        """
        カスタムメッセージが空値の場合は空欄として表示される
        """
        response = self._get()
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        # initial はフォームインスタンスの initial dict で確認
        self.assertFalse(form.initial.get("custom_message"))

    def test_response_does_not_contain_help_text_as_value(self):
        """レスポンスHTML中に "ChatGPTの自動メッセージ" が value として埋め込まれていない。"""
        response = self._get()
        content = response.content.decode("utf-8")
        # value 属性の中に紛れ込んでいないか（プレースホルダーとしての出現は許容しない）
        self.assertNotIn('value="ChatGPTの自動メッセージ"', content)
        self.assertNotIn("value='ChatGPTの自動メッセージ'", content)


# ---------------------------------------------------------------------------
# View POST → DB: 保存値の回帰テスト
# ---------------------------------------------------------------------------

class CustomMessageEditViewSaveTest(TestCase):
    """フォーム経由のPOSTがDBに正しい値を保存することを検証する。"""

    @classmethod
    def setUpTestData(cls):
        cls.teacher, cls.student = _make_org_teacher_student("view_save")

    def setUp(self):
        # 各テストで独立したリマインダーを作成（状態汚染を防ぐ）
        self.reminder = StudyReminder.objects.create(
            student=self.student,
            day_of_week="monday",
            time_of_day=time(9, 0),
            custom_message=None,
        )
        self.client.force_login(self.teacher)

    def _post(self, custom_message):
        return self.client.post(
            reverse("reminder_edit", kwargs={"pk": self.reminder.pk}),
            data={
                "day_of_week": "monday",
                "time_of_day": "09:00",
                "custom_message": custom_message,
                "learning_link_destination": "",
            },
        )

    def test_empty_post_saves_null(self):
        """
        空値のときは、Nullとして保存される
        """
        self._post("")
        self.reminder.refresh_from_db()
        self.assertIsNone(self.reminder.custom_message)

    def test_re_save_null_reminder_stays_null(self):
        """custom_message=None のリマインダーを空文字で再保存してもNULLのまま。"""
        self._post("")
        self.reminder.refresh_from_db()
        self.assertIsNone(self.reminder.custom_message)

        # 再度保存
        self._post("")
        self.reminder.refresh_from_db()
        self.assertIsNone(self.reminder.custom_message)

    def test_actual_message_post_saves_correctly(self):
        """
        実際のメッセージはそのまま保存される
        """
        self._post("今日も頑張ろう！")
        self.reminder.refresh_from_db()
        self.assertEqual(self.reminder.custom_message, "今日も頑張ろう！")
