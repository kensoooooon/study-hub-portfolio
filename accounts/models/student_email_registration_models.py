from django.db import models
from django.utils import timezone


class StudentEmailRegistrationToken(models.Model):
    """LINE経由のメールアドレス登録に使用する短命トークン。

    Notes:
        - raw token はURLに1度だけ載せる。DBには sha256 hash のみ保存する。
        - 同一 student の active token（used_at IS NULL AND revoked_at IS NULL）はUniqueConstraint で1件に制限する。
        - 実際にアクティブかの判定は使用期限も関わるが、DBに保存できないため、is_activeを呼び出すことで確認できるように
    """

    student = models.ForeignKey(
        "accounts.Student",
        on_delete=models.CASCADE,
        related_name="email_registration_tokens",
    )
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="email_registration_tokens",
    )
    line_user_id = models.CharField(max_length=255)

    # SHA-256 hex digest は常に64文字。unique=True でDBインデックスも兼ねる
    token_hash = models.CharField(max_length=64, unique=True)

    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student"],
                condition=models.Q(used_at__isnull=True, revoked_at__isnull=True),
                name="uq_active_student_email_registration_token_per_student",
            )
        ]

    @property
    def is_active(self) -> bool:
        now = timezone.now()
        return (
            self.used_at is None
            and self.revoked_at is None
            and self.expires_at >= now
        )

    def revoke(self, *, at=None) -> None:
        if self.revoked_at is not None:
            return
        self.revoked_at = at or timezone.now()
        self.save(update_fields=["revoked_at"])

    def mark_used(self, *, at=None) -> None:
        if self.used_at is not None:
            return
        self.used_at = at or timezone.now()
        self.save(update_fields=["used_at"])
