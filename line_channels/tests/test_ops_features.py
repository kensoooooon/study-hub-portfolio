# line_channels/tests/test_ops_features.py
from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.core.management import call_command, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from accounts.models import Organization
from line_channels.models import LineChannel, LineChannelKeyBundle, KeyKind
from line_channels.forms import ChannelSecretRotateForm, ChannelAccessTokenRotateForm
from line_channels.services import store_secret, get_secret


# -----------------------------
# 共通ヘルパ
# -----------------------------
def _create_org_and_channel(*, org_name="Test Org") -> tuple[Organization, LineChannel]:
    org = Organization.objects.create(name=org_name)
    ch = LineChannel.objects.create(
        organization=org,
        channel_id="abcdefg",
        bot_user_id="U" + "a" * 32,
        is_active=True,
    )
    return org, ch


def _create_user(*, email: str, role="teacher", username="U", password="testpass123"):
    User = get_user_model()
    return User.objects.create_user(
        email=email,
        password=password,
        role=role,
        username=username,
        is_first_login=False,
    )


def _setup_ops_group() -> Group:
    call_command("setup_ops_groups")
    return Group.objects.get(name="ops_line_channels")


# KMS を使わずに暗号系を通すモック（既存テストと同じ方向性）
KMS_WRAP = lambda b: b"WRAPPED_" + b
KMS_UNWRAP = lambda b: b.replace(b"WRAPPED_", b"")


# ---------------------------------------------------------
# 管理コマンド: give / revoke
# （setup_ops_groups の内容確認は既存で実装済み前提なので、
# ここは「ユーザーへの付与・剥奪」の挙動に絞る）
class OpsLineChannelsGrantRevokeCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _create_user(email="ops@example.com", username="Ops")
        _setup_ops_group()

    def test_give_permission_adds_user_to_group_and_is_idempotent(self):
        out = StringIO()
        call_command("give_permission_manage_channels", "--email", "OPS@EXAMPLE.COM", stdout=out)
        self.assertTrue(self.user.groups.filter(name="ops_line_channels").exists())

        # 2回目も成功（冪等）: 例外が出ない + 所属したまま
        out2 = StringIO()
        call_command("give_permission_manage_channels", "--email", "ops@example.com", stdout=out2)
        self.assertTrue(self.user.groups.filter(name="ops_line_channels").exists())

    def test_revoke_permission_removes_user_from_group_and_is_idempotent(self):
        g = Group.objects.get(name="ops_line_channels")
        self.user.groups.add(g)

        out = StringIO()
        call_command("revoke_permission_manage_channels", "--email", "ops@example.com", stdout=out)
        self.assertFalse(self.user.groups.filter(name="ops_line_channels").exists())

        # 2回目も成功（冪等）: 例外が出ない
        out2 = StringIO()
        call_command("revoke_permission_manage_channels", "--email", "ops@example.com", stdout=out2)
        self.assertFalse(self.user.groups.filter(name="ops_line_channels").exists())

    def test_give_permission_raises_when_user_missing(self):
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command("give_permission_manage_channels", "--email", "missing@example.com", stdout=out)

    def test_revoke_permission_raises_when_user_missing(self):
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command("revoke_permission_manage_channels", "--email", "missing@example.com", stdout=out)


# ---------------------------------------------------------
# Form: チャンネルシークレット / アクセストークン
# （既存テストと重複しないよう、入力検証を中心に）
# ---------------------------------------------------------
class RotateFormsValidationTests(TestCase):
    def test_channel_secret_confirm_mismatch_is_invalid(self):
        f = ChannelSecretRotateForm(
            data={"new_channel_secret": "a" * 30, "new_channel_secret_confirm": "b" * 30}
        )
        self.assertFalse(f.is_valid())
        self.assertIn("new_channel_secret_confirm", f.errors)

    def test_access_token_confirm_mismatch_is_invalid(self):
        """
        NOTE:
        ChannelAccessTokenRotateForm.clean() の confirm 参照バグを検出する目的。
        現状コードだとここが失敗する可能性あり（= テストが赤くなる）。
        """
        f = ChannelAccessTokenRotateForm(
            data={
                "new_channel_access_token": "a" * 30,
                "new_channel_access_token_confirm": "b" * 30,
            }
        )
        self.assertFalse(f.is_valid())
        self.assertIn("new_channel_access_token_confirm", f.errors)

    def test_access_token_rejects_whitespace(self):
        f = ChannelAccessTokenRotateForm(
            data={
                "new_channel_access_token": "abc def",
                "new_channel_access_token_confirm": "abc def",
            }
        )
        self.assertFalse(f.is_valid())
        self.assertIn("new_channel_access_token", f.errors)

    def test_access_token_rejects_too_short(self):
        f = ChannelAccessTokenRotateForm(
            data={
                "new_channel_access_token": "a" * 10,
                "new_channel_access_token_confirm": "a" * 10,
            }
        )
        self.assertFalse(f.is_valid())
        self.assertIn("new_channel_access_token", f.errors)


# ---------------------------------------------------------
# View: 認可 + 主要動作（activate/deactivate, rotate access token）
# ---------------------------------------------------------
class LineChannelViewsBehaviorTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._p_wrap = patch("line_channels.services.wrap_dek_with_kms", lambda b: b"WRAPPED_" + b)
        cls._p_unwrap = patch("line_channels.services.unwrap_dek_with_kms", lambda b: b.replace(b"WRAPPED_", b""))
        cls._p_wrap.start()
        cls._p_unwrap.start()

    @classmethod
    def tearDownClass(cls):
        cls._p_unwrap.stop()
        cls._p_wrap.stop()
        super().tearDownClass()

    def setUp(self):
        self.org, self.ch = _create_org_and_channel()
        self.user_no_perms = _create_user(email="no@example.com", username="NoPerms", role="teacher")
        self.user_ops = _create_user(email="ops@example.com", username="Ops", role="teacher")

        g = _setup_ops_group()
        self.user_ops.groups.add(g)

    def test_list_requires_permission(self):
        url = reverse("line_channels:list")

        self.client.login(email=self.user_no_perms.email, password="testpass123")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        self.client.logout()

        self.client.login(email=self.user_ops.email, password="testpass123")
        r2 = self.client.get(url)
        self.assertEqual(r2.status_code, 200)

    def test_detail_requires_permission(self):
        url = reverse("line_channels:detail", kwargs={"pk": self.ch.pk})

        self.client.login(email=self.user_no_perms.email, password="testpass123")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

        self.client.logout()

        self.client.login(email=self.user_ops.email, password="testpass123")
        r2 = self.client.get(url)
        self.assertEqual(r2.status_code, 200)

    def test_activate_deactivate_toggle(self):
        self.client.login(email=self.user_ops.email, password="testpass123")

        # deactivate
        url_deactivate = reverse("line_channels:deactivate", kwargs={"pk": self.ch.pk})
        r = self.client.post(url_deactivate)
        self.assertEqual(r.status_code, 302)
        self.ch.refresh_from_db()
        self.assertFalse(self.ch.is_active)

        # activate
        url_activate = reverse("line_channels:activate", kwargs={"pk": self.ch.pk})
        r2 = self.client.post(url_activate)
        self.assertEqual(r2.status_code, 302)
        self.ch.refresh_from_db()
        self.assertTrue(self.ch.is_active)

    def test_rotate_access_token_creates_new_bundle_and_retires_old_and_get_secret_roundtrip(self):
        """
        - AccessToken ローテで旧 active が退役する（CHANNEL_SECRET ではなく ACCESS_TOKEN を対象）
        - get_secret() で復号できる
        """
        # 事前に v1 を登録
        kb1 = store_secret(self.ch, KeyKind.ACCESS_TOKEN, b"token-v1")
        self.assertTrue(kb1.is_active)

        self.client.login(email=self.user_ops.email, password="testpass123")

        url = reverse("line_channels:rotate_channel_access_token", kwargs={"pk": self.ch.pk})
        payload = "token-v2-xxxxxxxxxxxxxxxxxxxx"  # 20+ chars
        r = self.client.post(
            url,
            data={
                "new_channel_access_token": payload,
                "new_channel_access_token_confirm": payload,
            },
            follow=False,
        )
        self.assertEqual(r.status_code, 302)

        # 新しい active が1件
        kb2 = LineChannelKeyBundle.objects.get(line_channel=self.ch, kind=KeyKind.ACCESS_TOKEN, is_active=True)
        self.assertNotEqual(kb2.pk, kb1.pk)

        # 旧が退役している
        old = LineChannelKeyBundle.objects.get(pk=kb1.pk)
        self.assertFalse(old.is_active)
        self.assertIsNotNone(old.rotated_at)

        # get_secret で最新値が取れる（bytes）
        pt = get_secret(self.ch, KeyKind.ACCESS_TOKEN)
        self.assertEqual(pt, payload.encode("utf-8"))

    def test_rotate_access_token_denies_without_manage_permission(self):
        url = reverse("line_channels:rotate_channel_access_token", kwargs={"pk": self.ch.pk})

        self.client.login(email=self.user_no_perms.email, password="testpass123")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_rotate_access_token_rejects_invalid_form_and_renders_200(self):
        """
        invalid POST は 200 でフォーム再表示（FormView標準）
        """
        self.client.login(email=self.user_ops.email, password="testpass123")

        url = reverse("line_channels:rotate_channel_access_token", kwargs={"pk": self.ch.pk})
        r = self.client.post(
            url,
            data={
                "new_channel_access_token": "abc def",
                "new_channel_access_token_confirm": "abc def",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "空白や改行を含まない値を入力してください。")
