"""
暗号の処理、およびGoogle KMSの操作を行う


"""
# line_channels/crypto.py
from __future__ import annotations
from typing import Optional, Tuple
import os
import logging

from django.conf import settings

# pip install cryptography google-cloud-kms
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from google.cloud import kms_v1
from google.api_core.retry import Retry

logger = logging.getLogger(__name__)

# ====== 暗号パラメータ ======
DEK_SIZE = 32          # 256-bit AES key
NONCE_SIZE = 12        # AES-GCM は 12 bytes nonce が推奨
_AESGCM_AAD: Optional[bytes] = None  # 付加認証データ(AAD)が必要ならここで設定

# ====== 例外 ======
class CryptoError(RuntimeError):
    pass

# ====== KMS クライアントのシングルトン ======
_kms_client: Optional[kms_v1.KeyManagementServiceClient] = None

def _get_kms_client() -> kms_v1.KeyManagementServiceClient:
    """KMS関連の操作を行うためのクライアントを確実に取得するためのヘルパー関数
    
    Returns:
        _kms_client (KeyManagementServiceClient): クライアント
    """
    global _kms_client
    if _kms_client is None:
        # gRPCが動作しないローカルにおいて、RESTモードに変形させる
        force_rest = (os.name == "nt") and (getattr(settings, "ENV", "local") == "local")
        transport = "rest" if force_rest else None
        _kms_client = kms_v1.KeyManagementServiceClient(transport=transport)
    return _kms_client


def _get_kms_key_resource() -> str:
    """KMSの名前を設定から取得するヘルパー関数
    
    Returns:
        key_name (str): 鍵の名前
    """
    key_name = getattr(settings, "LINE_KMS_KEY_RESOURCE", None)
    if not key_name:
        raise CryptoError("settings.LINE_KMS_KEY_RESOURCE が未設定です。")
    # 形式: projects/{p}/locations/{l}/keyRings/{r}/cryptoKeys/{k}
    if "/cryptoKeys/" not in key_name:
        raise CryptoError("LINE_KMS_KEY_RESOURCE の形式が不正です。")
    return key_name

# ====== DEK 生成 ======
def generate_dek() -> bytes:
    """ランダムな 32B の DEK を生成。"""
    return os.urandom(DEK_SIZE)

# ====== AES-GCM ======
def encrypt_with_dek(dek: bytes, plaintext: bytes, aad: Optional[bytes] = _AESGCM_AAD) -> Tuple[bytes, bytes]:
    """
    AES-GCMで平文をDEK（32B）を用いて暗号化する。

    Args:
        dek (bytes): Data Encryption Key（データ暗号化用の鍵, 32B）
        plaintext (bytes): 暗号化したい平文
        aad (Optional[bytes]): Additional Authenticated Data（追加認証データ）。
            暗号化はされないが、認証タグに含まれて完全性が保証される。
            復号時には暗号化時と**同一の値**を渡す必要がある。
            例：b"{org_id}:{channel_uuid}:{kind}"

    Returns:
        Tuple[bytes, bytes]: (nonce, ciphertext)
            - nonce: 12Bの使い捨てIV。秘密ではないが**再利用禁止**（同一DEKで使い回さない）。
            - ciphertext: 暗号文本体。末尾に16Bの認証タグが付与される（AESGCMの仕様）。

    Raises:
        CryptoError: 入力不正または暗号処理に失敗した場合
    """
    if not isinstance(plaintext, (bytes, bytearray)):
        raise CryptoError("plaintext は bytes で指定してください。")
    if len(dek) != DEK_SIZE:
        raise CryptoError(f"DEKのサイズが不正です: {len(dek)}B（期待値: {DEK_SIZE}B）")

    nonce = os.urandom(NONCE_SIZE)
    aesgcm = AESGCM(dek)
    ciphertext = aesgcm.encrypt(nonce, bytes(plaintext), aad)
    return nonce, ciphertext


def decrypt_with_dek(dek: bytes, nonce: bytes, ciphertext: bytes, aad: Optional[bytes] = _AESGCM_AAD) -> bytes:
    """
    AES-GCMで暗号文をDEKを用いて復号する。

    Args:
        dek (bytes): Data Encryption Key（32B）
        nonce (bytes): 暗号化時に使用した12BのIV（使い捨て）。**同一DEKでの再利用は不可**。
        ciphertext (bytes): 認証タグ付きの暗号文（末尾16Bがタグ）
        aad (Optional[bytes]): 追加認証データ。暗号化時と**同一の値**を渡す必要がある。

    Returns:
        bytes: 復号された平文

    Raises:
        CryptoError: 復号に失敗した場合（タグ検証失敗や入力不正など）
    """
    if len(dek) != DEK_SIZE:
        raise CryptoError(f"DEKのサイズが不正です: {len(dek)}B（期待値: {DEK_SIZE}B）")
    if len(nonce) != NONCE_SIZE:
        raise CryptoError(f"Nonce のサイズが不正です: {len(nonce)}B（期待値: {NONCE_SIZE}B）")

    aesgcm = AESGCM(dek)
    try:
        return aesgcm.decrypt(nonce, ciphertext, aad)
    except Exception as e:
        raise CryptoError("AES-GCM 復号に失敗しました。") from e

# ====== KMS (DEK の wrap/unwrap) ======
# ここでは対称鍵の“Encrypt/Decrypt” APIを使って DEK をそのまま包む（封筒暗号）
# ※ KMS 側の鍵は purpose=encryption の対称鍵であること
def wrap_dek_with_kms(dek: bytes) -> bytes:
    """
    DEK を KMS で暗号化（wrap）。戻り値は wrapped_dek（bytes）。
    呼び出しには roles/cloudkms.cryptoKeyEncrypter が必要。
    """
    key_name = _get_kms_key_resource()
    client = _get_kms_client()

    try:
        resp = client.encrypt(
            request={"name": key_name, "plaintext": dek},
            retry=Retry(deadline=10.0),
            timeout=10.0,
        )
        return resp.ciphertext
    except Exception as e:
        raise CryptoError("KMS での DEK 暗号化（wrap）に失敗しました。") from e

    
def unwrap_dek_with_kms(wrapped_dek: bytes) -> bytes:
    """
    KMS で DEK を復号（unwrap）。戻り値は平文の DEK（bytes）。
    呼び出しには roles/cloudkms.cryptoKeyDecrypter が必要。
    """
    key_name = _get_kms_key_resource()
    client = _get_kms_client()

    # ★ BinaryField 由来の memoryview 対策
    wrapped_bytes = bytes(wrapped_dek)

    try:
        resp = client.decrypt(
            request={"name": key_name, "ciphertext": wrapped_bytes},
            retry=Retry(deadline=10.0),
            timeout=10.0,
        )
        dek = resp.plaintext
        if len(dek) != DEK_SIZE:
            raise CryptoError(
                f"KMS から復号された DEK のサイズが不正です: {len(dek)}B"
            )
        return dek
    except Exception as e:
        raise CryptoError("KMS での DEK 復号（unwrap）に失敗しました。") from e


# ====== 安全メモ: “なんちゃって”ゼロ化（Pythonの制約付き） ======
def best_effort_zeroize(b: bytearray) -> None:
    """
    可能なら bytearray に対して上書きして解放。
    ※ CPython の最適化や GC で完全消去は保証できません。
    """
    try:
        for i in range(len(b)):
            b[i] = 0
    except Exception:
        pass
