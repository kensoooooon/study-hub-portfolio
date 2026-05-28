from django.test import SimpleTestCase

from accounts.services.normalize_email import normalize_email


class NormalizeEmailTests(SimpleTestCase):
    def test_returns_none_for_none(self):
        self.assertIsNone(normalize_email(None))

    def test_returns_none_for_non_string(self):
        self.assertIsNone(normalize_email(123))  # type: ignore[arg-type]

    def test_returns_empty_string_for_whitespace_only(self):
        self.assertEqual(normalize_email("   "), "")

    def test_trims_and_lowercases_email(self):
        self.assertEqual(
            normalize_email("  TEST@Example.COM  "),
            "test@example.com",
        )