"""
study_reminder.services.learning_link_availability の単体テスト。
DB あり・mock なし。
has_vocab_progress は実際の StudentContextProgress で判定する。
"""
from django.test import TestCase

from accounts.models import Organization, Student
from vocab_trainer.models import (
    Chapter,
    EnglishWord,
    JapaneseMeaning,
    StudentContextProgress,
    Textbook,
    WordMeaningContext,
    WordMeaningRelation,
)

from study_reminder.services.learning_link_availability import (
    LearningLinkAvailability,
    check_learning_link_availability,
)


class CheckLearningLinkAvailabilityTest(TestCase):
    """check_learning_link_availability() の全ケースを実 DB Student で確認する。"""

    @classmethod
    def setUpTestData(cls):
        org = Organization.objects.create(name="avail_test_org")

        cls.student_no_email = Student.objects.create_user(
            username="avail_no_email",
            email=None,
            password="pass",
            organization=org,
            is_active=True,
            line_user_id="avail_dummy_uid_no_email",
        )
        cls.student_no_vocab = Student.objects.create_user(
            username="avail_no_vocab",
            email="avail_no_vocab@example.com",
            password="pass",
            organization=org,
            is_active=True,
            line_user_id="avail_dummy_uid_no_vocab",
        )
        cls.student_with_vocab = Student.objects.create_user(
            username="avail_with_vocab",
            email="avail_with_vocab@example.com",
            password="pass",
            organization=org,
            is_active=True,
            line_user_id="avail_dummy_uid_with_vocab",
        )

        # StudentContextProgress 作成チェーン
        word = EnglishWord.objects.create(word="apple_avail")
        meaning = JapaneseMeaning.objects.create(meaning="りんご")
        relation = WordMeaningRelation.objects.create(english_word=word, japanese_meaning=meaning)
        textbook = Textbook.objects.create(name="Avail Book", publisher="Publisher", grade=1)
        chapter = Chapter.objects.create(textbook=textbook, title="Chapter 1", order=1)
        context = WordMeaningContext.objects.create(relation=relation, chapter=chapter, grade=1)
        StudentContextProgress.objects.create(
            student=cls.student_with_vocab, context=context, total_count=1
        )

    # --- destination が空 ---

    def test_empty_destination_not_allowed(self):
        result = check_learning_link_availability(self.student_no_email, destination="")
        self.assertFalse(result.allowed)

    # --- email なし ---

    def test_no_email_student_home_not_allowed(self):
        result = check_learning_link_availability(self.student_no_email, destination="student_home")
        self.assertFalse(result.allowed)

    def test_no_email_reason_contains_keyword(self):
        """既存テストが log.output で確認するキーワードが reason に含まれること。"""
        result = check_learning_link_availability(self.student_no_email, destination="student_home")
        self.assertIn("メールアドレスがありません", result.reason)

    def test_no_email_read_textbook_not_allowed(self):
        result = check_learning_link_availability(self.student_no_email, destination="read_textbook")
        self.assertFalse(result.allowed)

    # --- 未知の destination ---

    def test_unknown_destination_not_allowed(self):
        result = check_learning_link_availability(self.student_no_vocab, destination="math_trainer")
        self.assertFalse(result.allowed)

    # --- email あり + student_home ---

    def test_student_home_with_email_allowed(self):
        result = check_learning_link_availability(self.student_no_vocab, destination="student_home")
        self.assertTrue(result.allowed)

    # --- email あり + vocab 進捗なし ---

    def test_read_textbook_no_vocab_not_allowed(self):
        result = check_learning_link_availability(self.student_no_vocab, destination="read_textbook")
        self.assertFalse(result.allowed)

    def test_listening_eiken_no_vocab_not_allowed(self):
        result = check_learning_link_availability(
            self.student_no_vocab, destination="listening_eiken"
        )
        self.assertFalse(result.allowed)

    # --- email あり + vocab 進捗あり ---

    def test_read_textbook_with_vocab_allowed(self):
        result = check_learning_link_availability(
            self.student_with_vocab, destination="read_textbook"
        )
        self.assertTrue(result.allowed)

    def test_read_eiken_with_vocab_allowed(self):
        result = check_learning_link_availability(
            self.student_with_vocab, destination="read_eiken"
        )
        self.assertTrue(result.allowed)

    def test_listening_textbook_with_vocab_allowed(self):
        result = check_learning_link_availability(
            self.student_with_vocab, destination="listening_textbook"
        )
        self.assertTrue(result.allowed)

    def test_listening_eiken_with_vocab_allowed(self):
        result = check_learning_link_availability(
            self.student_with_vocab, destination="listening_eiken"
        )
        self.assertTrue(result.allowed)

    # --- 戻り値の型・内容 ---

    def test_return_type_is_dataclass(self):
        result = check_learning_link_availability(self.student_no_vocab, destination="student_home")
        self.assertIsInstance(result, LearningLinkAvailability)

    def test_allowed_true_has_empty_reason(self):
        result = check_learning_link_availability(self.student_no_vocab, destination="student_home")
        self.assertTrue(result.allowed)
        self.assertEqual(result.reason, "")
