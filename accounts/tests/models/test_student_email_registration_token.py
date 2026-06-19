"""
StudentEmailRegistrationToken モデルのテスト。

is_active プロパティ、revoke()、mark_used() の各メソッドと
DB 制約（token_hash unique、active token per student の UniqueConstraint）を検証する。
"""
from __future__ import annotations

import hashlib
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import Organization, Student, StudentEmailRegistrationToken


def _make_hash(value: str = "dummy") -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class StudentEmailRegistrationTokenModelTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="テスト組織")
        self.student = Student.objects.create(
            username="テスト生徒",
            line_user_id="U_test_001",
            organization=self.org,
        )

    def _make_token(self, **kwargs) -> StudentEmailRegistrationToken:
        defaults = {
            "student": self.student,
            "organization": self.org,
            "line_user_id": "U_test_001",
            "token_hash": _make_hash("raw_token_default"),
            "expires_at": timezone.now() + timedelta(minutes=15),
        }
        defaults.update(kwargs)
        return StudentEmailRegistrationToken.objects.create(**defaults)

    # ── is_active ──────────────────────────────────────────────────────────

    def test_is_active_true_for_fresh_token(self):
        """未使用・未revoke・期限内のトークンは is_active=True になる。"""
        token = self._make_token()
        self.assertTrue(token.is_active)

    def test_is_active_false_when_used(self):
        """used_at が設定されたトークンは is_active=False になる。"""
        token = self._make_token(used_at=timezone.now())
        self.assertFalse(token.is_active)

    def test_is_active_false_when_revoked(self):
        """revoked_at が設定されたトークンは is_active=False になる。"""
        token = self._make_token(revoked_at=timezone.now())
        self.assertFalse(token.is_active)

    def test_is_active_false_when_expired(self):
        """expires_at が過去のトークンは is_active=False になる。"""
        token = self._make_token(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertFalse(token.is_active)

    # ── revoke() ───────────────────────────────────────────────────────────

    def test_revoke_sets_revoked_at(self):
        """revoke() を呼ぶと revoked_at が設定される。"""
        token = self._make_token()
        now = timezone.now()

        token.revoke(at=now)
        token.refresh_from_db()

        self.assertEqual(token.revoked_at, now)

    def test_revoke_is_idempotent(self):
        """revoke() を複数回呼んでも最初の時刻が維持される。"""
        token = self._make_token()
        first = timezone.now()
        second = first + timedelta(minutes=5)

        token.revoke(at=first)
        token.revoke(at=second)
        token.refresh_from_db()

        self.assertEqual(token.revoked_at, first)

    # ── mark_used() ────────────────────────────────────────────────────────

    def test_mark_used_sets_used_at(self):
        """mark_used() を呼ぶと used_at が設定される。"""
        token = self._make_token()
        now = timezone.now()

        token.mark_used(at=now)
        token.refresh_from_db()

        self.assertEqual(token.used_at, now)

    def test_mark_used_is_idempotent(self):
        """mark_used() を複数回呼んでも最初の時刻が維持される。"""
        token = self._make_token()
        first = timezone.now()
        second = first + timedelta(minutes=5)

        token.mark_used(at=first)
        token.mark_used(at=second)
        token.refresh_from_db()

        self.assertEqual(token.used_at, first)

    # ── DB 制約 ─────────────────────────────────────────────────────────────

    def test_token_hash_must_be_unique(self):
        """同一 token_hash で2件作成しようとすると IntegrityError になる。"""
        same_hash = _make_hash("same_raw")
        self._make_token(token_hash=same_hash)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StudentEmailRegistrationToken.objects.create(
                    student=self.student,
                    organization=self.org,
                    line_user_id="U_test_001",
                    token_hash=same_hash,
                    expires_at=timezone.now() + timedelta(minutes=15),
                )

    def test_only_one_active_token_per_student(self):
        """同一 student に active token（used_at IS NULL AND revoked_at IS NULL）は1件のみ。"""
        self._make_token(token_hash=_make_hash("first"))

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StudentEmailRegistrationToken.objects.create(
                    student=self.student,
                    organization=self.org,
                    line_user_id="U_test_001",
                    token_hash=_make_hash("second"),
                    expires_at=timezone.now() + timedelta(minutes=15),
                )

    def test_can_create_new_token_after_revoke(self):
        """既存 active token を revoke すれば、同一 student に新規 token を作成できる。"""
        first = self._make_token(token_hash=_make_hash("first"))
        first.revoke()

        StudentEmailRegistrationToken.objects.create(
            student=self.student,
            organization=self.org,
            line_user_id="U_test_001",
            token_hash=_make_hash("second"),
            expires_at=timezone.now() + timedelta(minutes=15),
        )

    def test_can_create_new_token_after_used(self):
        """既存 token を mark_used すれば、同一 student に新規 token を作成できる。"""
        first = self._make_token(token_hash=_make_hash("first"))
        first.mark_used()

        StudentEmailRegistrationToken.objects.create(
            student=self.student,
            organization=self.org,
            line_user_id="U_test_001",
            token_hash=_make_hash("second"),
            expires_at=timezone.now() + timedelta(minutes=15),
        )
