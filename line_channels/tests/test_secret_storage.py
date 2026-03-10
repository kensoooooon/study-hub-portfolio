"""
新しいチャンネルシークレットを登録した際に、古いものがローテーションで退役されるかをテスト
"""
from unittest.mock import patch
from django.test import TestCase
from line_channels.models import LineChannel, LineChannelKeyBundle, KeyKind
from line_channels.services import store_secret


from accounts.models import Organization


class StoreSecretRotatesActiveKeyTests(TestCase):
    def setUp(self):
        organization = Organization.objects.create(
            name="dummy-organizaiton"
        )
        self.ch = LineChannel.objects.create(
            organization=organization,
            channel_id="abcdefg",
            bot_user_id="U" + "a" * 32,  # ← ダミーだが仕様準拠
        )

    @patch("line_channels.services.wrap_dek_with_kms", lambda b: b"WRAPPED_"+b)
    @patch("line_channels.services.unwrap_dek_with_kms", lambda b: b.replace(b"WRAPPED_", b""))
    def test_store_rotates_old_active(self):
        # 初回登録
        kb1 = store_secret(self.ch, KeyKind.CHANNEL_SECRET, b"v1")
        # 2回目で旧が退役
        kb2 = store_secret(self.ch, KeyKind.CHANNEL_SECRET, b"v2")
        self.assertTrue(kb2.is_active)
        old = LineChannelKeyBundle.objects.get(pk=kb1.pk)
        self.assertFalse(old.is_active)
        self.assertIsNotNone(old.rotated_at)
