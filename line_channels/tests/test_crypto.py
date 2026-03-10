"""
DEKを使った暗号化と復号が正常に行われているかをテスト
"""
from unittest.mock import patch
from django.test import TestCase

from line_channels.crypto import encrypt_with_dek, decrypt_with_dek


class DekEncryptionRoundTripTests(TestCase):
    @patch("line_channels.services.wrap_dek_with_kms", lambda b: b"WRAPPED_"+b)
    @patch("line_channels.services.unwrap_dek_with_kms", lambda b: b.replace(b"WRAPPED_", b""))
    def test_encrypt_decrypt(self):
        dek_plain = b"x"*32
        # 直接は使わないが、モックの整合を確認
        ch_plain = b"secret"
        nonce, ct = encrypt_with_dek(dek_plain, ch_plain)
        pt = decrypt_with_dek(dek_plain, nonce, ct)
        self.assertEqual(pt, ch_plain)