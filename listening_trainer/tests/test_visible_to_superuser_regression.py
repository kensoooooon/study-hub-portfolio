"""
Issue #162 回帰テスト: listening_trainer/models.py の各 *QuerySet.visible_to() から
`if user.is_superuser: return qs` の早期 return を撤去したことを固定する。

is_superuser フラグが立っていても、可視範囲は role とテナントスコープのみで
決まり、他組織の生徒が作成したデータは見えないことを確認する。
is_superuser=True の行は CheckConstraint により生成できないため、
メモリ上のインスタンスにフラグを立てて検証する。
"""
from django.test import TestCase

from accounts.models import Organization, OrganizationAdministrator, Student
from listening_trainer.models import (
    ListeningAnswer,
    ListeningPassage,
    ListeningQuestion,
    StudentListeningPassageProgress,
)


class ListeningTrainerVisibleToSuperuserRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="org1")
        cls.org2 = Organization.objects.create(name="org2")

        cls.org1_admin = OrganizationAdministrator.objects.create_user(
            email="org1_admin@example.com",
            username="org1_admin",
            password="pass12345",
            organization=cls.org1,
        )

        cls.org1_student = Student.objects.create_user(
            username="org1_student",
            email="org1_student@example.com",
            password="pass12345",
            organization=cls.org1,
            is_active=True,
        )
        cls.org2_student = Student.objects.create_user(
            username="org2_student",
            email="org2_student@example.com",
            password="pass12345",
            organization=cls.org2,
            is_active=True,
        )

        cls.passage_org1 = cls._make_passage(cls.org1_student, "p1")
        cls.passage_org2 = cls._make_passage(cls.org2_student, "p2")

        cls.question_org1 = cls._make_question(cls.passage_org1)
        cls.question_org2 = cls._make_question(cls.passage_org2)

        cls.answer_org1 = cls._make_answer(cls.org1_student, cls.question_org1)
        cls.answer_org2 = cls._make_answer(cls.org2_student, cls.question_org2)

        cls.progress_org1 = StudentListeningPassageProgress.objects.create(
            student=cls.org1_student, passage=cls.passage_org1
        )
        cls.progress_org2 = StudentListeningPassageProgress.objects.create(
            student=cls.org2_student, passage=cls.passage_org2
        )

    @staticmethod
    def _make_passage(student, title):
        return ListeningPassage.objects.create(
            title=title, content="body", created_by=student
        )

    @staticmethod
    def _make_question(passage):
        return ListeningQuestion.objects.create(
            passage=passage,
            question_text="q",
            option_a="a",
            option_b="b",
            option_c="c",
            option_d="d",
            correct_option="A",
            explanation="e",
        )

    @staticmethod
    def _make_answer(student, question):
        return ListeningAnswer.objects.create(
            student=student,
            question=question,
            selected_option="A",
            is_correct=True,
        )

    def setUp(self):  # 毎回実行されるsuperuserへの一時的変更
        self.su_admin = OrganizationAdministrator.objects.get(pk=self.org1_admin.pk)
        self.su_admin.is_superuser = True  # DB へは保存しない

    def test_passage_visible_to_is_not_widened_by_is_superuser(self):
        """
        ListeningPassageQuerySet.visible_to: is_superuser でも他組織の長文は見えない。
        """
        qs = ListeningPassage.objects.visible_to(self.su_admin)
        self.assertIn(self.passage_org1, qs)
        self.assertNotIn(self.passage_org2, qs)

    def test_question_visible_to_is_not_widened_by_is_superuser(self):
        """
        ListeningQuestionQuerySet.visible_to: is_superuser でも他組織の設問は見えない。
        """
        qs = ListeningQuestion.objects.visible_to(self.su_admin)
        self.assertIn(self.question_org1, qs)
        self.assertNotIn(self.question_org2, qs)

    def test_answer_visible_to_is_not_widened_by_is_superuser(self):
        """
        ListeningAnswerQuerySet.visible_to: is_superuser でも他組織の解答は見えない。
        """
        qs = ListeningAnswer.objects.visible_to(self.su_admin)
        self.assertIn(self.answer_org1, qs)
        self.assertNotIn(self.answer_org2, qs)

    def test_progress_visible_to_is_not_widened_by_is_superuser(self):
        """
        StudentListeningPassageProgressQuerySet.visible_to: is_superuser でも
        他組織の進捗は見えない。
        """
        qs = StudentListeningPassageProgress.objects.visible_to(self.su_admin)
        self.assertIn(self.progress_org1, qs)
        self.assertNotIn(self.progress_org2, qs)
