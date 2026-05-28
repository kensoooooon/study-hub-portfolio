from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from urllib.parse import parse_qs, urlparse


from line_integration.services.learning_links import (
    InvalidDestination,
    build_absolute_url,
    build_line_message,
    get_learning_path,
    get_login_redirect_path,
)


class LearningLinksTests(TestCase):
    def test_get_learning_path_valid_destination(self):
        path = get_learning_path("student_home")
        self.assertEqual(path, reverse("student:home"))

    def test_get_learning_path_all_valid_destinations(self):
        keys = [
            "student_home",
            "read_textbook",
            "read_eiken",
            "listening_textbook",
            "listening_eiken",
        ]
        for key in keys:
            with self.subTest(key=key):
                path = get_learning_path(key)
                self.assertTrue(path.startswith("/"), f"{key} should return an internal path")

    def test_get_learning_path_invalid_destination_raises(self):
        with self.assertRaises(InvalidDestination):
            get_learning_path("nonexistent_key")

    def test_get_learning_path_result_is_internal_path(self):
        path = get_learning_path("read_textbook")
        self.assertFalse(path.startswith("http"), "path should be internal, not absolute URL")

    def test_get_login_redirect_path_contains_login_and_next(self):
        """
        パースされたURLに正しくnextが設定されている
        """
        path = get_login_redirect_path("student_home")
        login_path = reverse("accounts_auth:login")
        next_path = reverse("student:home")

        parsed = urlparse(path)
        query = parse_qs(parsed.query)

        self.assertEqual(parsed.path, login_path)
        self.assertIn("next", query)
        self.assertEqual(query["next"], [next_path])

    def test_get_login_redirect_path_next_is_not_external_url(self):
        path = get_login_redirect_path("student_home")
        self.assertNotIn("http://", path)
        self.assertNotIn("https://", path)

    @override_settings(APP_PUBLIC_BASE_URL="https://example.com")
    def test_build_absolute_url_without_request_uses_settings(self):
        url = build_absolute_url("/some/path/")
        self.assertEqual(url, "https://example.com/some/path/")

    @override_settings(APP_PUBLIC_BASE_URL="https://example.com/")
    def test_build_absolute_url_trims_trailing_slash_from_base(self):
        url = build_absolute_url("/path/")
        self.assertEqual(url, "https://example.com/path/")

    def test_build_absolute_url_with_request_uses_build_absolute_uri(self):
        factory = RequestFactory()
        request = factory.get("/")
        url = build_absolute_url("/some/path/", request=request)
        self.assertIn("/some/path/", url)
        self.assertTrue(url.startswith("http"))

    @override_settings(APP_PUBLIC_BASE_URL="https://example.com")
    def test_build_line_message_contains_absolute_url(self):
        message = build_line_message("student_home")
        self.assertIn("https://example.com", message)
        self.assertIn(reverse("accounts_auth:login"), message)

    @override_settings(APP_PUBLIC_BASE_URL="https://example.com")
    def test_build_line_message_default_destination_is_student_home(self):
        message_default = build_line_message()
        message_explicit = build_line_message("student_home")
        self.assertEqual(message_default, message_explicit)

    def test_build_line_message_invalid_destination_raises(self):
        with self.assertRaises(InvalidDestination):
            build_line_message("unknown_destination")

    def test_get_login_redirect_path_invalid_destination_raises(self):
        with self.assertRaises(InvalidDestination):
            get_login_redirect_path("unknown")