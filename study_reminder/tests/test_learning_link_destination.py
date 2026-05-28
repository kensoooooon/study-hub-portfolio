"""
Tests for StudyReminder.learning_link_destination feature.

Covers:
- Model default value
- send_notification() conditional link insertion
- Form email guard (choices restriction and clean() validation)
- View: GET student check, POST save/reject
- Destination definition / LEARNING_DESTINATIONS consistency
- Vocab-progress-based form choices and send_notification
"""
from datetime import time
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import (
    Classroom,
    Organization,
    Student,
    Teacher,
)
from vocab_trainer.models import (
    Chapter,
    EnglishWord,
    JapaneseMeaning,
    StudentContextProgress,
    Textbook,
    WordMeaningContext,
    WordMeaningRelation,
)
from study_reminder.forms import StudyReminderCreateForm, StudyReminderEditForm
from study_reminder.models import StudyReminder


# ---------------------------------------------------------------------------
# Model default
# ---------------------------------------------------------------------------

class LearningLinkDestinationDefaultTest(TestCase):
    def setUp(self):
        org = Organization.objects.create(name="org_default")
        self.student = Student.objects.create_user(
            username="s_default", email="s_default@example.com", password="pass",
            organization=org, is_active=True, line_user_id="uid_default",
        )

    def test_default_is_empty_string(self):
        r = StudyReminder.objects.create(
            student=self.student,
            day_of_week="monday",
            time_of_day=time(9, 0),
        )
        self.assertEqual(r.learning_link_destination, "")


# ---------------------------------------------------------------------------
# send_notification()
# ---------------------------------------------------------------------------

class SendNotificationLinkTest(TestCase):
    """
    send_notification のリンク付与ロジックを検証する。
    Pub/Sub 送信・トークン復号はすべてモックで置き換える。
    """

    def setUp(self):
        org = Organization.objects.create(name="org_send")
        self.student_with_email = Student.objects.create_user(
            username="send_with_email", email="send_with@example.com", password="pass",
            organization=org, is_active=True, line_user_id="uid_send1",
        )
        self.student_no_email = Student.objects.create_user(
            username="send_no_email", email=None, password="pass",
            organization=org, is_active=True, line_user_id="uid_send_no_email",
        )

    def _mock_context(self):
        """共通モックのコンテキストマネージャーをまとめて返す。"""
        return [
            patch.object(StudyReminder, "resolve_line_channel", return_value=MagicMock()),
            patch("study_reminder.models.get_secret", return_value=b"token"),
            patch("study_reminder.models.PubSubPublisher.publish"),
            patch("study_reminder.models.MessageService.generate_message", return_value="base msg"),
            patch("study_reminder.models.ChatProcessor"),
        ]

    def test_no_destination_skips_link(self):
        """learning_link_destination="" のとき build_line_message が呼ばれない。"""
        reminder = StudyReminder(
            student=self.student_with_email,
            day_of_week="monday",
            time_of_day=time(9, 0),
            learning_link_destination="",
        )

        patches = self._mock_context()
        mocks = [p.start() for p in patches]
        try:
            with patch("study_reminder.models.build_line_message") as mock_build:
                result = reminder.send_notification()
        finally:
            for p in patches:
                p.stop()

        self.assertTrue(result)
        mock_build.assert_not_called()
        publish_mock = mocks[2]
        sent_msg = publish_mock.call_args[0][2]["custom_message"]
        self.assertEqual(sent_msg, "base msg")

    def test_destination_with_email_appends_link(self):
        """learning_link_destination="student_home" + email あり → リンクが付く。"""
        reminder = StudyReminder(
            student=self.student_with_email,
            day_of_week="monday",
            time_of_day=time(9, 0),
            learning_link_destination="student_home",
        )

        patches = self._mock_context()
        mocks = [p.start() for p in patches]
        try:
            with patch("study_reminder.models.build_line_message", return_value="LINK") as mock_build:
                result = reminder.send_notification()
        finally:
            for p in patches:
                p.stop()

        self.assertTrue(result)
        mock_build.assert_called_once_with("student_home")
        publish_mock = mocks[2]
        sent_msg = publish_mock.call_args[0][2]["custom_message"]
        self.assertIn("base msg", sent_msg)
        self.assertIn("LINK", sent_msg)

    def test_destination_without_email_skips_link_and_warns(self):
        """learning_link_destination="student_home" + email なし → リンクなし・warning。"""
        reminder = StudyReminder(
            student=self.student_no_email,
            day_of_week="monday",
            time_of_day=time(9, 0),
            learning_link_destination="student_home",
        )

        patches = self._mock_context()
        mocks = [p.start() for p in patches]
        try:
            with patch("study_reminder.models.build_line_message") as mock_build, \
                self.assertLogs("study_reminder.models", level="WARNING") as log:
                result = reminder.send_notification()
        finally:
            for p in patches:
                p.stop()

        self.assertTrue(result)
        mock_build.assert_not_called()
        publish_mock = mocks[2]
        sent_msg = publish_mock.call_args[0][2]["custom_message"]
        self.assertEqual(sent_msg, "base msg")
        self.assertTrue(any("メールアドレスがありません" in line for line in log.output))


# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------

class LearningLinkDestinationFormTest(TestCase):
    """フォームの email guard を検証する。"""

    def setUp(self):
        org = Organization.objects.create(name="org_form")
        self.student_with_email = Student.objects.create_user(
            username="form_with_email", email="form_with@example.com", password="pass",
            organization=org, is_active=True,
        )
        self.student_no_email = Student.objects.create_user(
            username="form_no_email", email=None, password="pass",
            organization=org, is_active=True, line_user_id="form_dummy_uid_no_email",
        )

    def _base_data(self, destination=""):
        return {
            "day_of_week": "monday",
            "time_of_day": "09:00",
            "custom_message": "",
            "learning_link_destination": destination,
        }

    def test_email_student_can_select_student_home(self):
        form = StudyReminderCreateForm(
            data=self._base_data("student_home"),
            student=self.student_with_email,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_no_email_student_choices_restricted_to_none(self):
        form = StudyReminderCreateForm(
            data=self._base_data(""),
            student=self.student_no_email,
        )
        choices = [v for v, _ in form.fields["learning_link_destination"].choices]
        self.assertEqual(choices, [""])

    def test_no_email_student_help_text_set(self):
        form = StudyReminderCreateForm(
            data=self._base_data(""),
            student=self.student_no_email,
        )
        self.assertIn("メールアドレスが登録されていない", form.fields["learning_link_destination"].help_text)

    def test_no_email_student_cannot_select_student_home(self):
        """email なし生徒に student_home を POST → form invalid。"""
        form = StudyReminderCreateForm(
            data=self._base_data("student_home"),
            student=self.student_no_email,
        )
        self.assertFalse(form.is_valid())

    def test_no_email_student_has_error_on_destination_field(self):
        """email なし生徒の場合、learning_link_destination にエラーが出る。"""
        form = StudyReminderCreateForm(
            data=self._base_data("student_home"),
            student=self.student_no_email,
        )
        form.is_valid()
        self.assertIn("learning_link_destination", form.errors)

    def test_edit_form_no_email_student_restricted(self):
        org = Organization.objects.create(name="org_form2")
        s = Student.objects.create_user(
            username="edit_form_with_email", email="edit_form@example.com", password="pass",
            organization=org, is_active=True,
        )
        reminder = StudyReminder.objects.create(
            student=s, day_of_week="monday", time_of_day=time(9, 0),
        )
        student_no_email = Student.objects.create_user(
            username="edit_form_no_email", email=None, password="pass",
            organization=org, is_active=True, line_user_id="edit_form_dummy_uid_no_email",
        )
        form = StudyReminderEditForm(
            data=self._base_data("student_home"),
            instance=reminder,
            student=student_no_email,
        )
        self.assertFalse(form.is_valid())

    def test_unknown_destination_is_rejected(self):
        """
        想定されていないリンク先が付与されている場合は拒否される
        """
        form = StudyReminderCreateForm(
            data=self._base_data("unknown_destination"),
            student=self.student_with_email,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("learning_link_destination", form.errors)


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

class ReminderCreateViewLinkTest(TestCase):
    """ReminderCreateView の GET/POST 時の学習リンク動作を検証する。"""

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="org_view_create")
        cls.classroom = Classroom.objects.create(name="cls_create", organization=cls.org)

        cls.teacher = Teacher.objects.create_user(
            username="teacher_create", email="teacher_create@example.com", password="pass",
            organization=cls.org,
        )
        cls.teacher.classrooms.add(cls.classroom)

        cls.student_with_email = Student.objects.create_user(
            username="view_with_email", email="view_with@example.com", password="pass",
            organization=cls.org, is_active=True, line_user_id="uid_view1",
        )
        cls.student_with_email.classrooms.add(cls.classroom)
        cls.student_with_email.teachers.add(cls.teacher)

        cls.student_no_email = Student.objects.create_user(
            username="view_no_email", email=None, password="pass",
            organization=cls.org, is_active=True, line_user_id="uid_view2",
        )
        cls.student_no_email.classrooms.add(cls.classroom)
        cls.student_no_email.teachers.add(cls.teacher)

    def _url(self, student):
        return f"{reverse('reminder_create')}?student={student.id}"

    def _post_data(self, destination=""):
        return {
            "day_of_week": "monday",
            "time_of_day": "09:00",
            "custom_message": "",
            "learning_link_destination": destination,
        }

    def test_get_checks_student_access(self):
        """GET 時点で student_access_check が走り、権限あり生徒ではフォームが返る。"""
        self.client.force_login(self.teacher)
        response = self.client.get(self._url(self.student_with_email))
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertIsInstance(form, StudyReminderCreateForm)

    def test_get_unauthorized_student_returns_403(self):
        """別 org の生徒 ID を指定すると GET 段階で 403。"""
        other_org = Organization.objects.create(name="other_org_create")
        other_student = Student.objects.create_user(
            username="other_s_create", email="o_create@example.com", password="pass",
            organization=other_org, is_active=True,
        )
        self.client.force_login(self.teacher)
        response = self.client.get(f"{reverse('reminder_create')}?student={other_student.id}")
        self.assertEqual(response.status_code, 403)

    def test_post_with_email_student_and_student_home_saves(self):
        """email あり生徒 + student_home → 保存される。"""
        self.client.force_login(self.teacher)
        before = StudyReminder.objects.filter(student=self.student_with_email).count()
        self.client.post(
            self._url(self.student_with_email),
            data=self._post_data("student_home"),
        )
        after = StudyReminder.objects.filter(student=self.student_with_email).count()
        self.assertEqual(after, before + 1)
        reminder = StudyReminder.objects.filter(student=self.student_with_email).latest("id")
        self.assertEqual(reminder.learning_link_destination, "student_home")

    def test_post_with_no_email_student_and_student_home_rejected(self):
        """email なし生徒 + student_home → 保存されない（フォームエラー）。"""
        self.client.force_login(self.teacher)
        before = StudyReminder.objects.filter(student=self.student_no_email).count()
        response = self.client.post(
            self._url(self.student_no_email),
            data=self._post_data("student_home"),
        )
        after = StudyReminder.objects.filter(student=self.student_no_email).count()
        self.assertEqual(after, before)
        self.assertEqual(response.status_code, 200)


class ReminderEditViewLinkTest(TestCase):
    """ReminderEditView でも learning_link_destination を変更できる。"""

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="org_view_edit")
        cls.classroom = Classroom.objects.create(name="cls_edit", organization=cls.org)
        cls.teacher = Teacher.objects.create_user(
            username="teacher_edit", email="teacher_edit@example.com", password="pass",
            organization=cls.org,
        )
        cls.teacher.classrooms.add(cls.classroom)

        cls.student = Student.objects.create_user(
            username="edit_view_student", email="edit_view@example.com", password="pass",
            organization=cls.org, is_active=True, line_user_id="uid_edit1",
        )
        cls.student.classrooms.add(cls.classroom)
        cls.student.teachers.add(cls.teacher)

        cls.reminder = StudyReminder.objects.create(
            student=cls.student,
            day_of_week="tuesday",
            time_of_day=time(10, 0),
            learning_link_destination="",
        )

    def test_edit_can_set_student_home(self):
        """編集画面で student_home に変更して保存できる。"""
        self.client.force_login(self.teacher)
        url = reverse("reminder_edit", kwargs={"pk": self.reminder.pk})
        self.client.post(url, data={
            "day_of_week": "tuesday",
            "time_of_day": "10:00",
            "custom_message": "",
            "learning_link_destination": "student_home",
        })
        self.reminder.refresh_from_db()
        self.assertEqual(self.reminder.learning_link_destination, "student_home")


# ---------------------------------------------------------------------------
# Destination definition
# ---------------------------------------------------------------------------

class LearningLinkDestinationDefinitionTest(TestCase):
    """LearningLinkDestination の値定義と LEARNING_DESTINATIONS の整合性を確認する。"""

    def test_expected_values_defined(self):
        LD = StudyReminder.LearningLinkDestination
        self.assertEqual(LD.READ_TEXTBOOK,      "read_textbook")
        self.assertEqual(LD.READ_EIKEN,         "read_eiken")
        self.assertEqual(LD.LISTENING_TEXTBOOK, "listening_textbook")
        self.assertEqual(LD.LISTENING_EIKEN,    "listening_eiken")

    def test_all_non_empty_destinations_in_learning_destinations(self):
        """NONE を除く全 LearningLinkDestination 値が LEARNING_DESTINATIONS に存在すること。"""
        from line_integration.services.learning_links import LEARNING_DESTINATIONS
        for dest in StudyReminder.LearningLinkDestination:
            if dest.value:
                self.assertIn(
                    dest.value,
                    LEARNING_DESTINATIONS,
                    f"{dest.value!r} は LEARNING_DESTINATIONS に存在しません",
                )


# ---------------------------------------------------------------------------
# Shared fixture helper for vocab progress tests
# ---------------------------------------------------------------------------

def _create_vocab_context():
    """StudentContextProgress 作成に必要な WordMeaningContext を生成して返す。"""
    word = EnglishWord.objects.create(word="apple_dest_test")
    meaning = JapaneseMeaning.objects.create(meaning="りんご")
    relation = WordMeaningRelation.objects.create(english_word=word, japanese_meaning=meaning)
    textbook = Textbook.objects.create(name="DestTest Book", publisher="Publisher", grade=1)
    chapter = Chapter.objects.create(textbook=textbook, title="Chapter 1", order=1)
    return WordMeaningContext.objects.create(relation=relation, chapter=chapter, grade=1)


# ---------------------------------------------------------------------------
# Form: vocab progress based choices (DB・mock なし)
# ---------------------------------------------------------------------------

class LearningLinkDestinationVocabFormTest(TestCase):
    """語彙進捗の有無による choices 絞り込みと clean() 拒否を検証する。"""

    @classmethod
    def setUpTestData(cls):
        org = Organization.objects.create(name="org_vocab_form_dest")
        cls.student_no_vocab = Student.objects.create_user(
            username="form_dest_no_vocab",
            email="form_dest_no_vocab@example.com",
            password="pass",
            organization=org,
            is_active=True,
        )
        cls.student_with_vocab = Student.objects.create_user(
            username="form_dest_with_vocab",
            email="form_dest_with_vocab@example.com",
            password="pass",
            organization=org,
            is_active=True,
        )
        context = _create_vocab_context()
        StudentContextProgress.objects.create(
            student=cls.student_with_vocab, context=context, total_count=1
        )

    def _base_data(self, destination=""):
        return {
            "day_of_week": "monday",
            "time_of_day": "09:00",
            "custom_message": "",
            "learning_link_destination": destination,
        }

    def test_email_no_vocab_choices_limited_to_none_and_student_home(self):
        """vocab 進捗なし → choices は リンクなし + 生徒ホーム のみ。"""
        form = StudyReminderCreateForm(
            data=self._base_data(""),
            student=self.student_no_vocab,
        )
        choices_values = [v for v, _ in form.fields["learning_link_destination"].choices]
        self.assertIn("", choices_values)
        self.assertIn("student_home", choices_values)
        self.assertNotIn("read_textbook", choices_values)
        self.assertNotIn("listening_eiken", choices_values)

    def test_email_with_vocab_all_choices_available(self):
        """vocab 進捗あり → read/listening 系 choices が含まれる。"""
        form = StudyReminderCreateForm(
            data=self._base_data(""),
            student=self.student_with_vocab,
        )
        choices_values = [v for v, _ in form.fields["learning_link_destination"].choices]
        self.assertIn("read_textbook",      choices_values)
        self.assertIn("read_eiken",         choices_values)
        self.assertIn("listening_textbook", choices_values)
        self.assertIn("listening_eiken",    choices_values)

    def test_no_vocab_cannot_post_read_textbook(self):
        """vocab 進捗なし生徒が read_textbook を POST → invalid。"""
        form = StudyReminderCreateForm(
            data=self._base_data("read_textbook"),
            student=self.student_no_vocab,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("learning_link_destination", form.errors)

    def test_with_vocab_can_post_read_textbook(self):
        """vocab 進捗あり生徒が read_textbook を POST → valid。"""
        form = StudyReminderCreateForm(
            data=self._base_data("read_textbook"),
            student=self.student_with_vocab,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_unknown_destination_rejected_even_with_vocab(self):
        """vocab 進捗ありでも unknown_destination は invalid。"""
        form = StudyReminderCreateForm(
            data=self._base_data("unknown_destination"),
            student=self.student_with_vocab,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("learning_link_destination", form.errors)


# ---------------------------------------------------------------------------
# View: vocab progress based create (DB・mock なし for availability)
# ---------------------------------------------------------------------------

class ReminderCreateViewVocabTest(TestCase):
    """create view の GET/POST で vocab 進捗による choices 制御を確認する。"""

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="org_view_vocab")
        cls.classroom = Classroom.objects.create(name="cls_vocab", organization=cls.org)
        cls.teacher = Teacher.objects.create_user(
            username="teacher_vocab", email="teacher_vocab@example.com", password="pass",
            organization=cls.org,
        )
        cls.teacher.classrooms.add(cls.classroom)

        cls.student_no_vocab = Student.objects.create_user(
            username="view_vocab_no",
            email="view_vocab_no@example.com",
            password="pass",
            organization=cls.org,
            is_active=True,
            line_user_id="uid_view_vocab_no",
        )
        cls.student_no_vocab.classrooms.add(cls.classroom)
        cls.student_no_vocab.teachers.add(cls.teacher)

        cls.student_with_vocab = Student.objects.create_user(
            username="view_vocab_yes",
            email="view_vocab_yes@example.com",
            password="pass",
            organization=cls.org,
            is_active=True,
            line_user_id="uid_view_vocab_yes",
        )
        cls.student_with_vocab.classrooms.add(cls.classroom)
        cls.student_with_vocab.teachers.add(cls.teacher)

        context = _create_vocab_context()
        StudentContextProgress.objects.create(
            student=cls.student_with_vocab, context=context, total_count=1
        )

    def _url(self, student):
        return f"{reverse('reminder_create')}?student={student.id}"

    def _post_data(self, destination=""):
        return {
            "day_of_week": "monday",
            "time_of_day": "09:00",
            "custom_message": "",
            "learning_link_destination": destination,
        }

    def test_get_form_choices_reflect_vocab_progress_no_vocab(self):
        """GET: vocab なし生徒のフォームに read/listening choices が含まれない。"""
        self.client.force_login(self.teacher)
        response = self.client.get(self._url(self.student_no_vocab))
        self.assertEqual(response.status_code, 200)
        choices_values = [
            v for v, _ in response.context["form"].fields["learning_link_destination"].choices
        ]
        self.assertNotIn("read_textbook", choices_values)

    def test_get_form_choices_reflect_vocab_progress_with_vocab(self):
        """GET: vocab あり生徒のフォームに read/listening choices が含まれる。"""
        self.client.force_login(self.teacher)
        response = self.client.get(self._url(self.student_with_vocab))
        self.assertEqual(response.status_code, 200)
        choices_values = [
            v for v, _ in response.context["form"].fields["learning_link_destination"].choices
        ]
        self.assertIn("read_textbook", choices_values)

    def test_post_no_vocab_read_textbook_not_saved(self):
        """POST: vocab なし + read_textbook → 保存されない。"""
        self.client.force_login(self.teacher)
        before = StudyReminder.objects.filter(student=self.student_no_vocab).count()
        response = self.client.post(
            self._url(self.student_no_vocab),
            data=self._post_data("read_textbook"),
        )
        after = StudyReminder.objects.filter(student=self.student_no_vocab).count()
        self.assertEqual(after, before)
        self.assertEqual(response.status_code, 200)

    def test_post_with_vocab_read_textbook_saved(self):
        """POST: vocab あり + read_textbook → 保存される。"""
        self.client.force_login(self.teacher)
        before = StudyReminder.objects.filter(student=self.student_with_vocab).count()
        self.client.post(
            self._url(self.student_with_vocab),
            data=self._post_data("read_textbook"),
        )
        after = StudyReminder.objects.filter(student=self.student_with_vocab).count()
        self.assertEqual(after, before + 1)
        reminder = StudyReminder.objects.filter(student=self.student_with_vocab).latest("id")
        self.assertEqual(reminder.learning_link_destination, "read_textbook")


# ---------------------------------------------------------------------------
# send_notification: vocab progress (外部サービスのみ mock、availability は mock なし)
# ---------------------------------------------------------------------------

class SendNotificationVocabProgressTest(TestCase):
    """send_notification() で read/listening 系 destination + vocab 進捗の有無を検証。
    外部送信系は mock する。availability（has_vocab_progress）は mock しない。
    """

    @classmethod
    def setUpTestData(cls):
        org = Organization.objects.create(name="org_notify_vocab")
        cls.student_no_vocab = Student.objects.create_user(
            username="notify_vocab_no",
            email="notify_vocab_no@example.com",
            password="pass",
            organization=org,
            is_active=True,
            line_user_id="uid_notify_no",
        )
        cls.student_with_vocab = Student.objects.create_user(
            username="notify_vocab_yes",
            email="notify_vocab_yes@example.com",
            password="pass",
            organization=org,
            is_active=True,
            line_user_id="uid_notify_yes",
        )
        context = _create_vocab_context()
        StudentContextProgress.objects.create(
            student=cls.student_with_vocab, context=context, total_count=1
        )

    def _mock_context(self):
        return [
            patch.object(StudyReminder, "resolve_line_channel", return_value=MagicMock()),
            patch("study_reminder.models.get_secret", return_value=b"token"),
            patch("study_reminder.models.PubSubPublisher.publish"),
            patch("study_reminder.models.MessageService.generate_message", return_value="base msg"),
            patch("study_reminder.models.ChatProcessor"),
        ]

    def _send(self, student, destination):
        reminder = StudyReminder(
            student=student,
            day_of_week="monday",
            time_of_day=time(9, 0),
            learning_link_destination=destination,
        )
        patches = self._mock_context()
        mocks = [p.start() for p in patches]
        try:
            with patch("study_reminder.models.build_line_message", return_value="LINK") as mock_build:
                result = reminder.send_notification()
        finally:
            for p in patches:
                p.stop()
        publish_mock = mocks[2]
        sent_msg = publish_mock.call_args[0][2]["custom_message"] if publish_mock.called else None
        return result, mock_build, sent_msg

    def test_student_home_no_vocab_calls_build_line_message(self):
        """student_home は vocab 進捗不要 → build_line_message("student_home") が呼ばれる。"""
        result, mock_build, sent_msg = self._send(self.student_no_vocab, "student_home")
        self.assertTrue(result)
        mock_build.assert_called_once_with("student_home")
        self.assertIn("LINK", sent_msg)

    def test_read_textbook_without_vocab_skips_link(self):
        """read_textbook + vocab 進捗なし → build_line_message は呼ばれない。"""
        result, mock_build, sent_msg = self._send(self.student_no_vocab, "read_textbook")
        self.assertTrue(result)
        mock_build.assert_not_called()
        self.assertEqual(sent_msg, "base msg")

    def test_read_textbook_with_vocab_appends_link(self):
        """read_textbook + vocab 進捗あり → build_line_message("read_textbook") が呼ばれる。"""
        result, mock_build, sent_msg = self._send(self.student_with_vocab, "read_textbook")
        self.assertTrue(result)
        mock_build.assert_called_once_with("read_textbook")
        self.assertIn("LINK", sent_msg)

    def test_listening_textbook_with_vocab_appends_link(self):
        """listening_textbook + vocab 進捗あり → build_line_message("listening_textbook") が呼ばれる。"""
        result, mock_build, sent_msg = self._send(self.student_with_vocab, "listening_textbook")
        self.assertTrue(result)
        mock_build.assert_called_once_with("listening_textbook")
