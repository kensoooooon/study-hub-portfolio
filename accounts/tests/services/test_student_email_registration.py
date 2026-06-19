"""
student_email_registration サービスのテスト。

is_email_registration_command、issue_email_registration_token、
get_token_by_raw、confirm_email_registration、
maybe_build_email_registration_response の各関数を検証する。
"""
from __future__ import annotations

import hashlib
from datetime import timedelta
from unittest.mock import MagicMock

from django.test import RequestFactory, TestCase
from django.utils import timezone
from django.urls import reverse

from accounts.models import BaseUser, Organization, Student, StudentEmailRegistrationToken
from accounts.services.exceptions import (
    StudentEmailAlreadyRegisteredError,
    StudentEmailConflictError,
    StudentEmailRegistrationTokenInactiveError,
    StudentEmailRegistrationTokenInvalidError,
)
from accounts.services.student_email_registration import (
    confirm_email_registration,
    get_token_by_raw,
    is_email_registration_command,
    issue_email_registration_token,
    maybe_build_email_registration_response,
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class IsEmailRegistrationCommandTests(TestCase):
    """is_email_registration_command の判定ロジックを検証する。"""

    def test_returns_true_for_mail_toroku(self):
        """「メール登録」は True を返す。"""
        self.assertTrue(is_email_registration_command("メール登録"))

    def test_returns_true_for_mail_address_toroku(self):
        """「メールアドレス登録」は True を返す。"""
        self.assertTrue(is_email_registration_command("メールアドレス登録"))

    def test_returns_true_with_surrounding_whitespace(self):
        """前後に空白があっても True を返す（strip() で対応）。"""
        self.assertTrue(is_email_registration_command("  メール登録  "))
        self.assertTrue(is_email_registration_command("\nメールアドレス登録\n"))

    def test_returns_false_for_ordinary_message(self):
        """通常のテキストメッセージは False を返す。"""
        self.assertFalse(is_email_registration_command("こんにちは"))

    def test_returns_false_for_partial_match(self):
        """部分一致は False を返す（厳密一致のみ）。"""
        self.assertFalse(is_email_registration_command("メール登録をお願いします"))


class IssueEmailRegistrationTokenTests(TestCase):
    """issue_email_registration_token のトークン発行ロジックを検証する。"""

    def setUp(self):
        self.org = Organization.objects.create(name="テスト組織")
        self.student = Student.objects.create(
            username="テスト生徒",
            line_user_id="U_issue_001",
            organization=self.org,
        )

    def _issue(self):
        return issue_email_registration_token(
            student=self.student,
            organization=self.org,
            line_user_id=self.student.line_user_id,
        )

    def test_returns_raw_token_string(self):
        """発行された raw token は空でない文字列である。"""
        raw = self._issue()
        self.assertIsInstance(raw, str)
        self.assertTrue(len(raw) > 0)

    def test_raw_token_not_stored_in_db(self):
        """raw token は DB に保存されない（token_hash != raw_token）。"""
        raw = self._issue()
        token = StudentEmailRegistrationToken.objects.get(token_hash=_hash(raw))
        self.assertNotEqual(token.token_hash, raw)

    def test_token_hash_is_sha256_of_raw_token(self):
        """DB に保存される token_hash は raw token の SHA-256 である。"""
        raw = self._issue()
        expected_hash = _hash(raw)
        self.assertTrue(
            StudentEmailRegistrationToken.objects.filter(token_hash=expected_hash).exists()
        )

    def test_old_active_token_is_revoked_on_new_issue(self):
        """新規発行時に同一 student の古い active token が revoke される。"""
        old_raw = self._issue()
        old_token = StudentEmailRegistrationToken.objects.get(token_hash=_hash(old_raw))
        self.assertIsNone(old_token.revoked_at)

        self._issue()

        old_token.refresh_from_db()
        self.assertIsNotNone(old_token.revoked_at)

    def test_only_one_active_token_exists_after_multiple_issues(self):
        """複数回発行しても active token（未使用・未revoke）は1件だけ存在する。"""
        self._issue()
        self._issue()
        self._issue()

        active_count = StudentEmailRegistrationToken.objects.filter(
            student=self.student,
            used_at__isnull=True,
            revoked_at__isnull=True,
        ).count()
        self.assertEqual(active_count, 1)


class GetTokenByRawTests(TestCase):
    """get_token_by_raw のトークン取得ロジックを検証する。"""

    def setUp(self):
        self.org = Organization.objects.create(name="テスト組織")
        self.student = Student.objects.create(
            username="テスト生徒",
            line_user_id="U_get_001",
            organization=self.org,
        )

    def test_returns_token_for_valid_raw_token(self):
        """有効な raw token から token record を取得できる。"""
        raw = issue_email_registration_token(
            student=self.student,
            organization=self.org,
            line_user_id=self.student.line_user_id,
        )
        token = get_token_by_raw(raw)
        self.assertEqual(token.student_id, self.student.pk)

    def test_raises_invalid_for_nonexistent_raw_token(self):
        """存在しない raw token は StudentEmailRegistrationTokenInvalidError になる。"""
        with self.assertRaises(StudentEmailRegistrationTokenInvalidError):
            get_token_by_raw("this_does_not_exist_in_db")


class ConfirmEmailRegistrationTests(TestCase):
    """confirm_email_registration の登録確定ロジックを検証する。"""

    def setUp(self):
        self.org = Organization.objects.create(name="テスト組織")
        self.student = Student.objects.create(
            username="テスト生徒",
            line_user_id="U_confirm_001",
            organization=self.org,
        )
        self.student.set_password("initial_pass_123")
        self.student.save(update_fields=["password"])

    def _issue(self):
        return issue_email_registration_token(
            student=self.student,
            organization=self.org,
            line_user_id=self.student.line_user_id,
        )

    def test_saves_student_email_on_success(self):
        """成功時に student.email が保存される。"""
        raw = self._issue()
        confirm_email_registration(raw_token=raw, email="new@example.com")

        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "new@example.com")

    def test_marks_token_used_on_success(self):
        """成功時に token.used_at が設定される。"""
        raw = self._issue()
        token = StudentEmailRegistrationToken.objects.get(token_hash=_hash(raw))
        self.assertIsNone(token.used_at)

        confirm_email_registration(raw_token=raw, email="new@example.com")

        token.refresh_from_db()
        self.assertIsNotNone(token.used_at)

    def test_password_not_changed_on_success(self):
        """成功時に student.password が変更されない。"""
        raw = self._issue()
        old_password = self.student.password

        confirm_email_registration(raw_token=raw, email="new@example.com")

        self.student.refresh_from_db()
        self.assertEqual(self.student.password, old_password)

    def test_normalizes_email_before_saving(self):
        """email は正規化（小文字化・strip）されてから保存される。"""
        raw = self._issue()
        confirm_email_registration(raw_token=raw, email="  NEW@EXAMPLE.COM  ")

        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "new@example.com")

    def test_raises_invalid_for_nonexistent_token(self):
        """存在しない raw token は StudentEmailRegistrationTokenInvalidError になる。"""
        with self.assertRaises(StudentEmailRegistrationTokenInvalidError):
            confirm_email_registration(raw_token="nonexistent", email="x@x.com")

    def test_raises_inactive_for_used_token(self):
        """使用済みトークンは StudentEmailRegistrationTokenInactiveError になる。"""
        raw = self._issue()
        token = StudentEmailRegistrationToken.objects.get(token_hash=_hash(raw))
        token.mark_used()

        with self.assertRaises(StudentEmailRegistrationTokenInactiveError):
            confirm_email_registration(raw_token=raw, email="x@x.com")

    def test_raises_inactive_for_revoked_token(self):
        """revoke 済みトークンは StudentEmailRegistrationTokenInactiveError になる。"""
        raw = self._issue()
        token = StudentEmailRegistrationToken.objects.get(token_hash=_hash(raw))
        token.revoke()

        with self.assertRaises(StudentEmailRegistrationTokenInactiveError):
            confirm_email_registration(raw_token=raw, email="x@x.com")

    def test_raises_inactive_for_expired_token(self):
        """期限切れトークンは StudentEmailRegistrationTokenInactiveError になる。"""
        raw = self._issue()
        token = StudentEmailRegistrationToken.objects.get(token_hash=_hash(raw))
        token.expires_at = timezone.now() - timedelta(seconds=1)
        token.save(update_fields=["expires_at"])

        with self.assertRaises(StudentEmailRegistrationTokenInactiveError):
            confirm_email_registration(raw_token=raw, email="x@x.com")

    def test_raises_inactive_for_inactive_student(self):
        """student.is_active=False なら StudentEmailRegistrationTokenInactiveError になる。"""
        raw = self._issue()
        self.student.is_active = False
        self.student.save(update_fields=["is_active"])

        with self.assertRaises(StudentEmailRegistrationTokenInactiveError):
            confirm_email_registration(raw_token=raw, email="x@x.com")

    def test_raises_inactive_for_organization_mismatch(self):
        """token.organization_id と student.organization_id が不一致ならエラーになる。"""
        other_org = Organization.objects.create(name="別組織")
        raw = self._issue()
        # token 発行後に student の organization を変更してズレを作る
        self.student.organization = other_org
        self.student.save(update_fields=["organization"])

        with self.assertRaises(StudentEmailRegistrationTokenInactiveError):
            confirm_email_registration(raw_token=raw, email="x@x.com")

    def test_raises_inactive_for_line_user_id_mismatch(self):
        """token.line_user_id と student.line_user_id が不一致ならエラーになる。"""
        raw = self._issue()
        # token 発行後に student の line_user_id を変更してズレを作る
        self.student.line_user_id = "U_changed_999"
        self.student.save(update_fields=["line_user_id"])

        with self.assertRaises(StudentEmailRegistrationTokenInactiveError):
            confirm_email_registration(raw_token=raw, email="x@x.com")

    def test_raises_already_registered_if_student_email_exists(self):
        """student.email がすでに設定済みなら StudentEmailAlreadyRegisteredError になる。"""
        self.student.email = "already@example.com"
        self.student.save(update_fields=["email"])
        raw = self._issue()

        with self.assertRaises(StudentEmailAlreadyRegisteredError):
            confirm_email_registration(raw_token=raw, email="new@example.com")

    def test_raises_conflict_if_email_used_by_another_user(self):
        """入力 email が既存 BaseUser.email と衝突すれば StudentEmailConflictError になる。"""
        BaseUser.objects.create_user(
            email="taken@example.com",
            password="pass",
            role="organization_administrator",
            username="別ユーザー",
        )
        raw = self._issue()

        with self.assertRaises(StudentEmailConflictError):
            confirm_email_registration(raw_token=raw, email="taken@example.com")

    def test_rollback_on_conflict_error(self):
        """email 衝突エラー時に student.email と token.used_at が変更されない。"""
        BaseUser.objects.create_user(
            email="taken2@example.com",
            password="pass",
            role="organization_administrator",
            username="別ユーザー2",
        )
        raw = self._issue()

        with self.assertRaises(StudentEmailConflictError):
            confirm_email_registration(raw_token=raw, email="taken2@example.com")

        self.student.refresh_from_db()
        self.assertFalse(self.student.email)

        token = StudentEmailRegistrationToken.objects.get(token_hash=_hash(raw))
        self.assertIsNone(token.used_at)


class MaybeBuildEmailRegistrationResponseTests(TestCase):
    """maybe_build_email_registration_response の応答生成ロジックを検証する。"""

    def setUp(self):
        self.org = Organization.objects.create(name="テスト組織")
        self.student = Student.objects.create(
            username="テスト生徒",
            line_user_id="U_maybe_001",
            organization=self.org,
        )
        self.factory = RequestFactory()
        self.line_channel = MagicMock()
        self.line_channel.organization = self.org
        self.line_channel.organization_id = self.org.pk

    def _call(self, message_text):
        request = self.factory.get("/")
        return maybe_build_email_registration_response(
            request=request,
            student=self.student,
            line_channel=self.line_channel,
            message_text=message_text,
        )

    def test_returns_none_for_non_command(self):
        """メール登録コマンド以外のメッセージは None を返す。"""
        result = self._call("こんにちは")
        self.assertIsNone(result)

    def test_returns_url_for_valid_command(self):
        """「メール登録」コマンドで登録 URL を含む文面を返す。"""
        result = self._call("メール登録")
        self.assertIsNotNone(result)
        self.assertIn("register_email", result)

    def test_returns_url_for_mail_address_command(self):
        """「メールアドレス登録」コマンドでも登録 URL を含む文面を返す。"""
        result = self._call("メールアドレス登録")
        self.assertIsNotNone(result)
        self.assertIn("register_email", result)

    def test_returns_already_registered_message_if_email_exists(self):
        """student.email が登録済みの場合は登録済みメッセージを返す。"""
        self.student.email = "existing@example.com"
        self.student.save(update_fields=["email"])

        result = self._call("メール登録")
        self.assertIsNotNone(result)
        self.assertIn("登録済み", result)

    def test_already_registered_response_contains_login_url(self):
        """登録済み返信にログインURLが含まれる。"""
        self.student.email = "existing@example.com"
        self.student.save(update_fields=["email"])

        result = self._call("メール登録")
        self.assertIn(reverse("accounts_auth:login"), result)

    def test_unregistered_response_contains_login_url(self):
        """未登録時の返信にもログインURLと事前案内が含まれる。"""
        result = self._call("メール登録")
        self.assertIn(reverse("accounts_auth:login"), result)
        self.assertIn("ログインできます", result)

    def test_returns_none_for_inactive_student(self):
        """inactive student に対しては None を返す（多重防御）。"""
        self.student.is_active = False
        self.student.save(update_fields=["is_active"])

        result = self._call("メール登録")
        self.assertIsNone(result)

    def test_url_contains_token_query_param(self):
        """返された URL に ?t= クエリパラメータが含まれる。"""
        result = self._call("メール登録")
        self.assertIn("?t=", result)

    def test_returns_none_for_organization_mismatch(self):
        """student と line_channel の organization が異なる場合は None を返す（多重防御）。"""
        other_org = Organization.objects.create(name="別組織")
        self.line_channel.organization = other_org
        self.line_channel.organization_id = other_org.pk

        result = self._call("メール登録")

        self.assertIsNone(result)

    def test_returns_none_for_organization_mismatch_even_if_email_exists(self):
        """別組織の student 状態は、email 登録済みでも返さない。"""
        other_org = Organization.objects.create(name="別組織")
        self.student.email = "existing@example.com"
        self.student.save(update_fields=["email"])

        self.line_channel.organization = other_org
        self.line_channel.organization_id = other_org.pk

        result = self._call("メール登録")

        self.assertIsNone(result)
