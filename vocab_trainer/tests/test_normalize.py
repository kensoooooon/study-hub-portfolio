from django.test import SimpleTestCase
from vocab_trainer.management.commands.utils import normalize_chapter_title


class NormalizeChapterTitleTests(SimpleTestCase):
    def test_basic_cases(self):
        self.assertEqual(normalize_chapter_title("Unit3"), "Unit 3")
        self.assertEqual(normalize_chapter_title("Unit10"), "Unit 10")
        self.assertEqual(normalize_chapter_title("Let'sTalk2"), "Let'sTalk 2")
        self.assertEqual(normalize_chapter_title("Unit 1-2"), "Unit 1 - 2")
        self.assertEqual(normalize_chapter_title("Stage Activity1"), "Stage Activity 1")
