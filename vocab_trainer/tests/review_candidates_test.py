from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from accounts.models import Student
from vocab_trainer.models import WordMeaningContext, StudentContextProgress, Textbook, Chapter, EnglishWord, JapaneseMeaning, WordMeaningRelation
from vocab_trainer.services import get_review_candidates_by_due


class ReviewCandidateSelectionTests(TestCase):

    def setUp(self):
        self.student = Student.objects.create(username="test_student", email="test@example.com")
        
        # 関連モデルの作成
        textbook = Textbook.objects.create(name="テスト教科書", publisher="テスト出版", grade=1, publication_year=2025)
        self.student.textbook = textbook
        self.student.save()

        chapter = Chapter.objects.create(textbook=textbook, title="Unit 1", order=1)
        en_word = EnglishWord.objects.create(word="test")
        jp_meaning = JapaneseMeaning.objects.create(meaning="テスト")
        relation = WordMeaningRelation.objects.create(english_word=en_word, japanese_meaning=jp_meaning)

        context1 = WordMeaningContext.objects.create(relation=relation, chapter=chapter, grade=1)
        context2 = WordMeaningContext.objects.create(relation=relation, chapter=chapter, grade=1)

        self.due_progress = StudentContextProgress.objects.create(
            student=self.student,
            context=context1,
            next_due_at=timezone.now() - timedelta(days=1),
            review_priority=0.9
        )

        self.future_progress = StudentContextProgress.objects.create(
            student=self.student,
            context=context2,
            next_due_at=timezone.now() + timedelta(days=3),
            review_priority=0.6
        )


    def test_due_candidates_are_prioritized(self):
        results = get_review_candidates_by_due(self.student, max_candidates=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.due_progress)

    def test_fallback_is_used_when_due_insufficient(self):
        results = get_review_candidates_by_due(self.student, max_candidates=2)
        self.assertEqual(len(results), 2)
        self.assertIn(self.due_progress, results)
        self.assertIn(self.future_progress, results)

    def test_max_candidates_limit_is_respected(self):
        results = get_review_candidates_by_due(self.student, max_candidates=1)
        self.assertEqual(len(results), 1)

