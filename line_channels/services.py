"""
暗号化をcrypto.pyに委託しつつ、LineChannelKeyBundleなどのDB関連の操作を実施する


"""

from django.db import transaction
from .models import LineChannel, LineChannelKeyBundle, KeyKind
from .crypto import generate_dek, encrypt_with_dek, wrap_dek_with_kms, unwrap_dek_with_kms, decrypt_with_dek
from django.utils import timezone

@transaction.atomic
def old_store_secret(line_channel, kind: KeyKind, plaintext: bytes) -> LineChannelKeyBundle:  # いきなり消すのは怖いので、old型で残す2026/1/19
    """ラインチャンネルに紐づけたシークレット情報を格納
    
    Args:
        line_channel (LineChannel): 対象となるラインチャンネル
        kind (KeyKind): 鍵の種類(現在はラインチャンネルシークレットorアクセストークン)
        plaintext (bytes): 暗号化する対象の平文
    """
    dek = generate_dek()
    aad = f"{line_channel.organization_id}:{line_channel.channel_id}:{kind}".encode()
    nonce, ciphertext = encrypt_with_dek(dek, plaintext, aad=aad)
    wrapped_dek = wrap_dek_with_kms(dek)
    kb = LineChannelKeyBundle.objects.create(
        line_channel=line_channel, kind=kind,
        secret_ciphertext=ciphertext, secret_nonce=nonce, secret_wrapped_dek=wrapped_dek,
        is_active=True,
    )
    (LineChannelKeyBundle.objects
        .filter(line_channel=line_channel, kind=kind, is_active=True)
        .exclude(pk=kb.pk)
        .select_for_update()
    ).update(is_active=False)
    return kb

@transaction.atomic
def store_secret(line_channel, kind: KeyKind, plaintext: bytes) -> LineChannelKeyBundle:
    """ラインチャンネルに紐づけたシークレット情報を格納
    
    Args:
        line_channel (LineChannel): 対象となるラインチャンネル
        kind (KeyKind): 鍵の種類(現在はラインチャンネルシークレットorアクセストークン)
        plaintext (bytes): 暗号化する対象の平文
    """
    # 1) 既存 active をロックして退役（先に！）
    (LineChannelKeyBundle.objects
        .select_for_update()
        .filter(line_channel=line_channel, kind=kind, is_active=True)
    ).update(is_active=False, rotated_at=timezone.now())

    # 2) 新規作成
    dek = generate_dek()
    aad = f"{line_channel.organization_id}:{line_channel.channel_id}:{kind}".encode()
    nonce, ciphertext = encrypt_with_dek(dek, plaintext, aad=aad)
    wrapped_dek = wrap_dek_with_kms(dek)

    kb = LineChannelKeyBundle.objects.create(
        line_channel=line_channel,
        kind=kind,
        secret_ciphertext=ciphertext,
        secret_nonce=nonce,
        secret_wrapped_dek=wrapped_dek,
        is_active=True,
    )
    return kb


def get_secret(line_channel: LineChannel, kind: KeyKind) -> bytes:
    """ラインチャンネルに紐づいた機密情報を取得し、復号し返す
    
    Args:
        line_channel (LineChannel): 対象のラインチャンネル
        kind (KeyKind): 鍵の種類(ラインチャンネルアクセストークンorラインチャンネルシークレット)
    """
    kb = LineChannelKeyBundle.objects.get(line_channel=line_channel, kind=kind, is_active=True)
    dek = unwrap_dek_with_kms(kb.secret_wrapped_dek)
    aad = f"{line_channel.organization_id}:{line_channel.channel_id}:{kind}".encode()
    return decrypt_with_dek(dek, kb.secret_nonce, kb.secret_ciphertext, aad=aad)
