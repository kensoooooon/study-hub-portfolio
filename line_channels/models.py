"""
Line Channel Access TokenとLine Channel Secretを安全に格納し、複数のチャンネル切り替えを実現するためのモデル構造

・封筒暗号
→暗号化
機密情報(ラインチャンネルアクセストークンやラインチャンネルシークレット）をDEK(Data Encryption Key)で暗号化
そのDEKをKEK(Key Encryption Key)で暗号化
平文のDEKは廃棄し、wrapped_dek(暗号化されたDEK)を残す
暗号化の際には使い切りのデータ(nonce)で暗号の多様性を確保する。こちらも保存

→復号
紐づけられたラインチャンネルの情報(bot_user_id, channel_id)からKEKを呼び出す
DEKを復号し、保存されたシークレット情報を復号する
"""
from __future__ import annotations

from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone


class LineChannel(models.Model):
    """
    LINE Messaging API チャンネルのメタ情報。
    - 組織 × bot_user_id (destination) で一意
    - 組織 × channel_id で一意
    - 機密値は LineChannelKeyBundle でローテーション管理
    
    Attributes:
        organization (models.ForeignKey): ラインチャンネルが紐づけられた組織
        channel_id (models.CharField): チャンネルのID
        bot_user_id (models.CharField): ボットのユーザーID
        is_active (models.BooleanField): 有効なチャンネルか否か
        metadata (models.JSONField): 今後追加する小さな情報の格納先(現在は任意)
        created_at (models.DateTimeField): 作成された日時
        updated_at (models.DateTimeField): いずれかのデータが更新された日時
    """
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.PROTECT, # 誤削除で孤児化を防ぐ
        related_name='line_channels',
        verbose_name='所属組織',
    )

    # LINE Developers の Channel ID（数値文字列だが厳格バリデーションはしない）
    channel_id = models.CharField(max_length=64, db_index=True, verbose_name='Channel ID')

    # webhook body "destination" に入る bot のユーザーID: 'U' + 32桁hex
    bot_user_id = models.CharField(
        max_length=34,
        db_index=True,
        validators=[RegexValidator(regex=r"^U[0-9a-f]{32}$")],
        help_text="webhookのdestinationに入るbotユーザーID（例: Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx）",
        verbose_name='BotユーザーID',
    )

    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)  # 任意：用途/備考/タグ等
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            # 想定される検索条件を指定し、検索を高速化
            models.Index(fields=['organization', 'bot_user_id']),
            models.Index(fields=['organization', 'channel_id']),
        ]
        constraints = [
            # 組織内で bot_user_id を一意に
            models.UniqueConstraint(
                fields=['organization', 'bot_user_id'],
                name='uq_org_bot_user_id',
            ),
            # 組織内で channel_id を一意に
            models.UniqueConstraint(
                fields=['organization', 'channel_id'],
                name='uq_org_channel_id',
            ),
        ]

        permissions = [  # モデルの操作に関する権限を設定。user.has_parm(permission)の形でbool判定可能
            # チャンネル作成/更新/無効化/secretローテなど、運用ユースケース全般
            ("manage_line_channels", "Can manage LINE channels (create/update/rotate secrets)"),
            # secretの「値」ではなく「登録済みか/更新日時などのメタ情報」だけ閲覧可能
            ("view_line_channel_secret_metadata", "Can view LINE channel secret metadata (not values)"),
        ]


    def __str__(self) -> str:
        return f"[{self.organization}] bot:{self.bot_user_id} ch:{self.channel_id}"


class KeyKind(models.TextChoices):
    """鍵の種類を規定(ラインチャンネルシークレットorラインチャンネルアクセストークン)
    """
    CHANNEL_SECRET = "CHANNEL_SECRET", "Channel Secret"
    ACCESS_TOKEN   = "ACCESS_TOKEN",   "Channel Access Token"


class LineChannelKeyBundle(models.Model):
    """ラインチャンネルに紐づけられる機密情報
    
    Attributes:
        secret_ciphertext (model.BinaryField): シークレットやトークンを暗号化したもの
        secret_nonce (models.BinaryField): 暗号化の際に用いられたナンス
        secret_wrapped_dek (models.BinaryField): 暗号化されたDEK
        is_active (models.BooleanField): バンドルが有効か否か
        rotated_at (models.DateTimeField): いつ情報がローテーションされたか
        metadata (models.JSONField): 様々な小さいメモ
        created_at (models.DateTimeField): 作成された日時
    
    封筒暗号で保管する機密値（シークレット/アクセストークン）のバンドル。
    - secret_ciphertext: 平文を DEK で暗号化したバイト列
    - secret_nonce: AEAD(GCM等) のノンス
    - secret_wrapped_dek: DEK を KEK(KMS等)でラップしたバイト列
    - kind: 値種別（CHANNEL_SECRET / ACCESS_TOKEN）
    - (line_channel, kind) で is_active=True は常に 1件
    """
    line_channel = models.ForeignKey(
        LineChannel,
        on_delete=models.CASCADE,        # 親チャンネル削除で鍵も削除
        related_name='key_bundles',
        verbose_name='チャンネル',
    )
    kind = models.CharField(max_length=32, choices=KeyKind.choices, db_index=True, verbose_name='鍵種別')

    # バイナリで保存（Base64で持つなら CharField に変更し十分な長さを確保）
    secret_ciphertext = models.BinaryField(verbose_name='暗号文')
    secret_nonce = models.BinaryField(verbose_name='ノンス')
    secret_wrapped_dek = models.BinaryField(verbose_name='ラップ済みDEK')

    is_active = models.BooleanField(default=True, db_index=True)
    rotated_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['line_channel', 'kind', 'is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['line_channel', 'kind'],
                name='uq_active_keybundle_per_kind',
                condition=models.Q(is_active=True),     # 条件付きユニークで現行1件を保証
            )
        ]

    def rotate_out(self) -> None:
        """この鍵バンドルを退役させる（is_active=False, rotated_at を付与）。"""
        if self.is_active:
            self.is_active = False
            self.rotated_at = timezone.now()
            self.save(update_fields=['is_active', 'rotated_at'])

    def __str__(self) -> str:
        status = "active" if self.is_active else "retired"
        return f"{self.line_channel} [{self.kind}] ({status})"
