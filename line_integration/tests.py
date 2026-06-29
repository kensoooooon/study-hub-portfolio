from unittest.mock import MagicMock, patch

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


# ── LINE Webhook メール登録コマンド分岐テスト ────────────────────────────────


class WebhookStudentOrganizationTests(TestCase):
    """LineWebhookView.handle_event() における Student 作成時の organization 設定を検証する。"""

    def setUp(self):
        from accounts.models import Organization, Student
        from line_integration.views import LineWebhookView

        self.factory = RequestFactory()
        self.view = LineWebhookView()
        self.org = Organization.objects.create(name="Webhook org テスト組織")
        self.ch = MagicMock()
        self.ch.organization = self.org
        self.ch.organization_id = self.org.pk
        self.ch.bot_user_id = "BOT_org_001"

    def _make_text_event(self, user_id: str) -> dict:
        return {
            "type": "message",
            "source": {"type": "user", "userId": user_id},
            "message": {"type": "text", "text": "こんにちは"},
            "replyToken": "reply_token_org_xxx",
        }

    def _handle(self, event):
        request = self.factory.get("/")
        return self.view.handle_event(request, event, "access_token_xxx", self.ch)

    def test_new_student_gets_organization_on_first_save(self):
        """新規 Student は handle_event() 呼び出し時に organization_id が初回保存に含まれる。"""
        from accounts.models import Student

        event = self._make_text_event("U_new_student_org")
        self._handle(event)

        student = Student.objects.get(line_user_id="U_new_student_org")
        self.assertEqual(student.organization_id, self.org.pk)

    def test_existing_student_organization_is_not_overwritten_rejected(self):
        """既存 Student の organization_id は get_or_create_userの仕様により上書きされず、登録済みとして拒否される"""
        from accounts.models import Organization, Student

        other_org = Organization.objects.create(name="別組織")
        Student.objects.create(
            username="既存生徒",
            line_user_id="U_existing_org",
            organization=other_org,
        )

        event = self._make_text_event("U_existing_org")
        response = self._handle(event)

        self.assertIn("別の教室アカウント", response)
        student = Student.objects.get(line_user_id="U_existing_org")
        self.assertEqual(student.organization_id, other_org.pk)

    @patch("processors.chat_processor.ChatProcessor.generate_response_text", return_value="AIの返答")
    def test_existing_same_organization_student_is_accepted(self, mock_chat):
        """
        すでに登録済みの同じ組織の生徒は、そのまま会話処理が行われる
        """
        from accounts.models import Student

        Student.objects.create(
            username="既存生徒",
            line_user_id="U_existing_same_org",
            organization=self.org,
        )

        event = self._make_text_event("U_existing_same_org")
        response = self._handle(event)

        self.assertEqual(response, "AIの返答")
        mock_chat.assert_called_once()


class WebhookEmailRegistrationBranchTests(TestCase):
    """LineWebhookView.handle_event() のメール登録コマンド分岐を検証する。

    外部 LINE API と ChatProcessor は mock して、分岐ロジックだけを確認する。
    """

    def setUp(self):
        from accounts.models import Organization, Student
        from line_integration.views import LineWebhookView

        self.factory = RequestFactory()
        self.view = LineWebhookView()

        self.org = Organization.objects.create(name="Webhook テスト組織")

        # 名前登録済み・active・email 未登録の標準生徒
        self.student = Student.objects.create(
            username="テスト生徒",
            line_user_id="U_webhook_001",
            organization=self.org,
        )

        # LineChannel の mock
        self.ch = MagicMock()
        self.ch.organization = self.org
        self.ch.organization_id = self.org.pk
        self.ch.bot_user_id = "BOT_001"

    def _make_text_event(self, text: str, user_id: str = "U_webhook_001") -> dict:
        return {
            "type": "message",
            "source": {"type": "user", "userId": user_id},
            "message": {"type": "text", "text": text},
            "replyToken": "reply_token_xxx",
        }

    def _handle(self, event):
        request = self.factory.get("/")
        return self.view.handle_event(request, event, "access_token_xxx", self.ch)

    def test_name_registration_takes_priority_over_email_command(self):
        """名前未登録の生徒には名前登録リンクが優先され、メール登録リンクは返らない。"""
        self.student.username = ""
        self.student.save(update_fields=["username"])

        response = self._handle(self._make_text_event("メール登録"))

        self.assertIn("お名前を登録してください", response)
        self.assertNotIn("register_email", response)

    @patch("processors.chat_processor.ChatProcessor.generate_response_text")
    def test_email_registration_command_returns_registration_link(self, mock_chat):
        """active・名前登録済み・email 未登録の生徒が「メール登録」を送ると登録リンクが返る。"""
        response = self._handle(self._make_text_event("メール登録"))

        self.assertIn("register_email", response)
        self.assertIn("?t=", response)
        mock_chat.assert_not_called()

    @patch("processors.chat_processor.ChatProcessor.generate_response_text")
    def test_email_already_registered_returns_registered_message(self, mock_chat):
        """email 登録済みの生徒が「メール登録」を送ると登録済みメッセージが返る。"""
        self.student.email = "existing@example.com"
        self.student.save(update_fields=["email"])

        response = self._handle(self._make_text_event("メール登録"))

        self.assertIn("登録済み", response)
        mock_chat.assert_not_called()

    @patch("processors.chat_processor.ChatProcessor.generate_response_text", return_value="AIの返答")
    def test_ordinary_message_passes_to_chat_processor(self, mock_chat):
        """通常テキストはメール登録コマンドと判定されず ChatProcessor に渡る。"""
        response = self._handle(self._make_text_event("数学を教えてください"))

        mock_chat.assert_called_once()
        self.assertEqual(response, "AIの返答")
    
    @patch("processors.chat_processor.ChatProcessor.generate_response_text")
    def test_inactive_student_is_rejected_before_email_registration_branch(self, mock_chat):
        """inactive 生徒はメール登録コマンドでも通常チャットへ流れず、無効化メッセージが返る。"""
        self.student.is_active = False
        self.student.save(update_fields=["is_active"])

        response = self._handle(self._make_text_event("メール登録"))

        self.assertIn("アカウントが無効化されています", response)
        self.assertIn("教室までご連絡ください", response)
        self.assertNotIn("register_email", response)
        mock_chat.assert_not_called()

    @patch("processors.chat_processor.ChatProcessor.generate_response_text")
    def test_different_organization_student_is_rejected_before_email_registration_branch(self, mock_chat):
        """別組織チャンネルからのメール登録コマンドは、メール登録処理に入らず拒否される。"""
        from accounts.models import Organization

        other_org = Organization.objects.create(name="別組織")
        self.student.organization = other_org
        self.student.save(update_fields=["organization"])

        response = self._handle(self._make_text_event("メール登録"))

        self.assertIn("別の教室アカウント", response)
        self.assertIn("教室までお問い合わせください", response)
        self.assertNotIn("register_email", response)
        mock_chat.assert_not_called()
