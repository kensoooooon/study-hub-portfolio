"""
メールを用いた各ロールのユーザーの招待を記録する

- 現状は組織管理者のみだが、ロールを拡張できる余地を残す

Note:
    nullはDBレベルの話、blankはフォームの話
"""

from django.db import models
from django.utils import timezone

from accounts.services.normalize_email import normalize_email


class InvitationRole(models.TextChoices):
    """
    招待するユーザーの対象となるロール
    """
    STUDENT = "student", "生徒"
    TEACHER = "teacher", "講師"
    CLASSROOM_ADMIN = "classroom_administrator", "教室管理者"
    ORG_ADMIN = "organization_administrator", "組織管理者"


class SendStatus(models.TextChoices):
    """
    メールの送信状態について記録
    招待の状態については別である点に注意
    """
    PENDING = "pending", "未送信"
    SENT = "sent", "送信成功"
    FAILED = "failed", "送信失敗"
    


class Invitation(models.Model):
    """
    メール送信を経由するユーザー招待の管理を行うモデル
    
    Attributes:
        organization: ユーザーの所属する組織
        role: 招待するユーザーのモデル
    """
    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, null=False, blank=False, related_name='invitations')  # 対象となる組織
    email = models.EmailField(null=False, blank=False, db_index=True, verbose_name="メールアドレス")
    role = models.CharField(max_length=50, choices=InvitationRole.choices)  # 招待した相手のロール
    
    created_at = models.DateTimeField(auto_now_add=True)  # 作成された日時(期限計算の起点)
    expires_at = models.DateTimeField(null=False, blank=False)  # 消費期限はいつまでか(自然の時間経過で切れる期限)
    used_at = models.DateTimeField(null=True, blank=True)  # いつ利用されたか
    revoked_at = models.DateTimeField(null=True, blank=True)  # いつ取り消されたか(自然の時間経過以外のもの)
    
    invited_by = models.ForeignKey("accounts.BaseUser", on_delete=models.PROTECT, related_name="sent_invitations")  # ログ削除ではなく、誰の操作か履歴が残るように

    send_status = models.CharField(max_length=30, choices=SendStatus.choices, default=SendStatus.PENDING)
    last_send_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"],  # 組織とメールでアクティブな招待は1つだけ。
                name="uq_active_email_per_organization",
                condition=models.Q(used_at__isnull=True, revoked_at__isnull=True),  # 静的条件で時刻は扱えないため、そちらは別途判定すること
            )
        ]
    
    def __str__(self):
        return f"<{self.organization}: {self.invited_by.email} -> {self.email}>"

    def save(self, *args, **kwargs):  # 保存時にも多重防御
        self.email = normalize_email(self.email)
        super().save(*args, **kwargs)

    @property  # obj.is_active()としなくて済むように
    def is_active(self):
        now = timezone.now()
        return (
            self.used_at is None and
            self.revoked_at is None and
            self.expires_at >= now
        )
    
    def revoke(self, *, at=None) -> None:
        if self.revoked_at is not None:
            return
        revoked_at = at or timezone.now()
        self.revoked_at = revoked_at
        self.save(update_fields=["revoked_at"])

    def mark_used(self, *, at=None) -> None:
        if self.used_at is not None:
            return
        used_at = at or timezone.now()
        self.used_at = used_at
        self.save(update_fields=["used_at"])

    def mark_send_succeeded(self, *, at=None) -> None:
        attempted_at = at or timezone.now()
        self.send_status = SendStatus.SENT
        self.last_send_attempt_at = attempted_at
        self.sent_at = attempted_at
        self.save(
            update_fields=[
                "send_status",
                "last_send_attempt_at",
                "sent_at",
            ]
        )

    def mark_send_failed(self, *, at=None) -> None:
        attempted_at = at or timezone.now()
        self.send_status = SendStatus.FAILED
        self.last_send_attempt_at = attempted_at
        self.save(
            update_fields=[
                "send_status",
                "last_send_attempt_at",
            ]
        )
