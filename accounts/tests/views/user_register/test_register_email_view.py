"""
RegisterEmailView のテスト。

GET / POST それぞれのシナリオを検証する。
トークン検証・フォーム処理・エラー分岐・成功レスポンスを網羅する。
"""
from __future__ import annotations

import hashlib
from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from accounts.models import BaseUser, Organization, Student, StudentEmailRegistrationToken
from accounts.services.student_email_registration import issue_email_registration_token
from accounts.services.exceptions import StudentEmailAlreadyRegisteredError

_URL = reverse("user_register:register_email")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class RegisterEmailViewGetTests(TestCase):
    """RegisterEmailView GET のシナリオを検証する。"""

    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(name="テスト組織")
        self.student = Student.objects.create(
            username="テスト生徒",
            line_user_id="U_view_get_001",
            organization=self.org,
        )

    def _issue(self):
        return issue_email_registration_token(
            student=self.student,
            organization=self.org,
            line_user_id=self.student.line_user_id,
        )

    def test_get_with_valid_token_returns_form(self):
        """有効なトークンで GET するとメール入力フォームが表示される（200）。"""
        raw = self._issue()
        resp = self.client.get(_URL + f"?t={raw}")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "メールアドレス登録")

    def test_get_without_token_returns_400(self):
        """トークンなしで GET すると無効リンク画面（400）が返る。"""
        resp = self.client.get(_URL)
        self.assertEqual(resp.status_code, 400)

    def test_get_with_invalid_token_returns_400(self):
        """存在しない raw token で GET すると無効リンク画面（400）が返る。"""
        resp = self.client.get(_URL + "?t=totally_invalid_token")
        self.assertEqual(resp.status_code, 400)

    def test_get_with_used_token_returns_400(self):
        """使用済みトークンで GET すると無効リンク画面（400）が返る。"""
        raw = self._issue()
        token = StudentEmailRegistrationToken.objects.get(token_hash=_hash(raw))
        token.mark_used()

        resp = self.client.get(_URL + f"?t={raw}")
        self.assertEqual(resp.status_code, 400)

    def test_get_with_expired_token_returns_400(self):
        """期限切れトークンで GET すると無効リンク画面（400）が返る。"""
        raw = self._issue()
        token = StudentEmailRegistrationToken.objects.get(token_hash=_hash(raw))
        token.expires_at = timezone.now() - timedelta(seconds=1)
        token.save(update_fields=["expires_at"])

        resp = self.client.get(_URL + f"?t={raw}")
        self.assertEqual(resp.status_code, 400)

    def test_get_with_revoked_token_returns_400(self):
        """revoke 済みトークンで GET すると無効リンク画面（400）が返る。"""
        raw = self._issue()
        token = StudentEmailRegistrationToken.objects.get(token_hash=_hash(raw))
        token.revoke()

        resp = self.client.get(_URL + f"?t={raw}")
        self.assertEqual(resp.status_code, 400)

    def test_get_with_already_registered_email_shows_registered_message(self):
        """student.email が登録済みの場合は登録済みメッセージを表示する（200）。"""
        self.student.email = "already@example.com"
        self.student.save(update_fields=["email"])
        raw = self._issue()

        resp = self.client.get(_URL + f"?t={raw}")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "登録済み")

    def test_already_registered_contains_login_url(self):
        """登録済み画面にログインURLが含まれる。"""
        self.student.email = "already@example.com"
        self.student.save(update_fields=["email"])
        raw = self._issue()

        resp = self.client.get(_URL + f"?t={raw}")
        self.assertContains(resp, reverse("accounts_auth:login"))

    def test_get_with_inactive_student_returns_400(self):
        """inactive な student に紐づくトークンで GET すると無効リンク画面（400）が返る。"""
        self.student.is_active = False
        self.student.save(update_fields=["is_active"])
        raw = self._issue()

        resp = self.client.get(_URL + f"?t={raw}")
        self.assertEqual(resp.status_code, 400)


class RegisterEmailViewPostTests(TestCase):
    """RegisterEmailView POST のシナリオを検証する。"""

    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(name="テスト組織")
        self.student = Student.objects.create(
            username="テスト生徒",
            line_user_id="U_view_post_001",
            organization=self.org,
        )
        self.student.set_password("initial_pass")
        self.student.save(update_fields=["password"])

    def _issue(self):
        return issue_email_registration_token(
            student=self.student,
            organization=self.org,
            line_user_id=self.student.line_user_id,
        )

    def _post(self, raw_token, email):
        return self.client.post(_URL, {"t": raw_token, "email": email})

    def test_post_with_valid_token_and_email_returns_success(self):
        """有効なトークンと有効な email で POST すると成功テンプレートが返る（200）。"""
        raw = self._issue()
        resp = self._post(raw, "new@example.com")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "登録完了")

    def test_post_success_contains_login_url(self):
        """成功画面にログインURLが含まれる。"""
        raw = self._issue()
        resp = self._post(raw, "new@example.com")
        self.assertContains(resp, reverse("accounts_auth:login"))

    def test_post_saves_email_to_student(self):
        """成功後に student.email が保存されている。"""
        raw = self._issue()
        self._post(raw, "saved@example.com")

        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "saved@example.com")

    def test_post_without_token_returns_400(self):
        """トークンなしで POST すると無効リンク画面（400）が返る。"""
        resp = self.client.post(_URL, {"email": "x@x.com"})
        self.assertEqual(resp.status_code, 400)

    def test_post_with_invalid_token_returns_400(self):
        """存在しない raw token で POST すると無効リンク画面（400）が返る。"""
        resp = self._post("invalid_token", "x@x.com")
        self.assertEqual(resp.status_code, 400)

    def test_post_with_invalid_email_shows_form_error(self):
        """不正な email フォーマットで POST するとフォームエラーが表示される（200 再表示）。"""
        raw = self._issue()
        resp = self._post(raw, "not-an-email")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "メールアドレス登録")

    def test_post_with_conflicting_email_shows_form_error(self):
        """他 BaseUser の email と衝突する場合はフォームエラーが表示される（200 再表示）。"""
        BaseUser.objects.create_user(
            email="taken@example.com",
            password="pass",
            role="organization_administrator",
            username="別ユーザー",
        )
        raw = self._issue()
        resp = self._post(raw, "taken@example.com")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "利用できません")

    def test_post_with_already_used_token_returns_400(self):
        """使用済みトークンで POST すると無効リンク画面（400）が返る。"""
        raw = self._issue()
        # 1回目は成功
        self._post(raw, "first@example.com")

        # 2回目の POST は同じトークンなので失敗
        resp = self._post(raw, "second@example.com")
        self.assertEqual(resp.status_code, 400)

    @patch(
        "accounts.views.line_email_registration_views.confirm_email_registration",
        side_effect=StudentEmailAlreadyRegisteredError,
    )
    def test_post_already_registered_contains_login_url(self, mock_confirm):
        """
        登録済みの場合もログインURLが含まれる
        """
        raw = self._issue()

        resp = self._post(raw, "existing@example.com")

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("accounts_auth:login"))
        self.assertContains(resp, "登録済み")