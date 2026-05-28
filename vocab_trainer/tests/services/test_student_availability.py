from django.test import TestCase

from accounts.models import Student, Organization, Classroom
from vocab_trainer.models import (
    EnglishWord,
    JapaneseMeaning,
    WordMeaningRelation,
    Textbook,
    Chapter,
    WordMeaningContext,
    StudentContextProgress,
)
from vocab_trainer.services.student_availability import has_vocab_progress


class HasVocabProgressTest(TestCase):
    """
    has_vocab_progressが正しく動作しているかを確かめるためのテスト
    """
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Org")
        cls.classroom = Classroom.objects.create(name="Classroom", organization=cls.org)

        cls.student = Student.objects.create_user(
            username="student1",
            email="student1@example.com",
            password="pass123456",
            organization=cls.org,
            is_active=True,
        )
        cls.inactive_student = Student.objects.create_user(
            username="inactive_student",
            email="inactive_student@example.com",
            password="pass123456",
            organization=cls.org,
            is_active=False,
        )

        word = EnglishWord.objects.create(word="apple")
        meaning = JapaneseMeaning.objects.create(meaning="りんご")
        relation = WordMeaningRelation.objects.create(english_word=word, japanese_meaning=meaning)
        textbook = Textbook.objects.create(name="Test Book", publisher="Test Publisher", grade=1)
        chapter = Chapter.objects.create(textbook=textbook, title="Chapter 1", order=1)
        cls.context = WordMeaningContext.objects.create(relation=relation, chapter=chapter, grade=1)

    def test_returns_false_when_no_progress(self):
        """
        進捗がない生徒はFalse
        """
        self.assertFalse(has_vocab_progress(self.student))

    def test_returns_false_when_total_count_is_zero(self):
        """
        進捗は存在しているが、取り組み回数が0の場合はFalse
        """
        StudentContextProgress.objects.create(
            student=self.student, context=self.context, total_count=0
        )
        self.assertFalse(has_vocab_progress(self.student))

    def test_returns_true_when_total_count_greater_than_zero(self):
        """
        取り組みが存在していて、かつ取り組み回数が0より大きければTrue
        """
        StudentContextProgress.objects.create(
            student=self.student, context=self.context, total_count=1
        )
        self.assertTrue(has_vocab_progress(self.student))

    def test_returns_false_for_inactive_student(self):
        """
        非アクティブ生徒はたとえ取り組み回数が0より大きくてもFalse
        """
        StudentContextProgress.objects.create(
            student=self.inactive_student, context=self.context, total_count=1
        )
        self.assertFalse(has_vocab_progress(self.inactive_student))
