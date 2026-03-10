from django.db import models
from accounts.models import Student

from study_reminder.services.message_service import MessageService
from processors.chat_processor import ChatProcessor
from study_reminder.utils.pubsub_publisher import PubSubPublisher

# 30分単位の変更
from django.core.exceptions import ValidationError

# ログ
import logging

# 曜日と時間の並び替え
from django.db.models import Case, When

# アクセス制御
from accounts.models import OrganizationAdministrator, ClassroomAdministrator, Teacher

# 追加 import（ファイル先頭の方）
from line_channels.models import LineChannel, KeyKind
from line_channels.services import get_secret

# pubsubのtopic読み出し用
from django.conf import settings

logger = logging.getLogger(__name__)

def validate_time_in_15_min_intervals(value):
    if value.minute % 15 != 0:
        raise ValidationError('時刻は15分単位で設定してください。')


class StudyReminderQuerySet(models.QuerySet):
    """
    曜日→時間の並び替え実現
    """
    def ordered_by_day_and_time(self):
        return self.order_by(
            Case(
                When(day_of_week='monday', then=1),
                When(day_of_week='tuesday', then=2),
                When(day_of_week='wednesday', then=3),
                When(day_of_week='thursday', then=4),
                When(day_of_week='friday', then=5),
                When(day_of_week='saturday', then=6),
                When(day_of_week='sunday', then=7),
            ),
            'time_of_day'
        )

    def filter_by_access(self, user):
        """
        ユーザーがアクセス可能な StudyReminder のみを返す QuerySet に絞り込む。
        - 組織管理者: 管理している組織に所属する生徒のリマインダー
        - 教室管理者: 自身が管理する教室に所属する生徒のリマインダー＋可能なら organization でも絞り込み
        - 講師      : 自身が担当している生徒のリマインダー＋可能なら organization でも絞り込み
        """
        role = getattr(user, "role", None)

        # 🏢 組織管理者
        if role == 'organization_administrator':
            admin = getattr(user, 'organizationadministrator', None)
            if admin:
                orgs = admin.organizations.all()
                if orgs.exists():
                    # 生徒の所属 organization を軸に絞り込み
                    return self.filter(student__organization__in=orgs)
            return self.none()

        # 🏫 教室管理者
        elif role == 'classroom_administrator':
            admin = getattr(user, 'classroomadministrator', None)
            if admin:
                qs = self.filter(student__classrooms__in=admin.classrooms.all())
                # ClassroomAdministrator.organization が入っている場合は
                # 組織でも二重に絞り込んで防御を厚くする
                org = getattr(admin, 'organization', None)
                if org is not None:
                    qs = qs.filter(student__organization=org)
                return qs
            return self.none()

        # 👨‍🏫 講師
        elif role == 'teacher':
            # まずは「担当している生徒」に紐づくリマインダー
            qs = self.filter(student__teachers=user)

            # Teacher.organization が設定済みなら、組織でも絞る
            # （Teacher.organization が None の既存データは現状の挙動を維持）
            org = getattr(user, 'organization', None)
            if org is not None:
                qs = qs.filter(student__organization=org)
            return qs

        # それ以外のロールには一切見せない
        return self.none()


class StudyReminder(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='study_reminders',
        help_text="このリマインダーが関連付けられている学生"
    )
    day_of_week = models.CharField(
        max_length=10,
        choices=[
            ('monday', '月曜日'),
            ('tuesday', '火曜日'),
            ('wednesday', '水曜日'),
            ('thursday', '木曜日'),
            ('friday', '金曜日'),
            ('saturday', '土曜日'),
            ('sunday', '日曜日'),
        ],
        help_text="通知する曜日（例: 月曜日、火曜日）。"
        )
    time_of_day = models.TimeField(
        help_text="通知の時間を15分間隔の24時間形式で設定します（例: 15:15, 14:30）。",
        validators=[validate_time_in_15_min_intervals]
    )
    is_active = models.BooleanField(
        default=True,
        help_text="このリマインダーが現在有効であるかを示します。"
    )
    custom_message = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="通知メッセージを任意に設定できます。未設定の場合、ChatGPTが生成したメッセージが使用されます。"
    )
    last_notified = models.DateField(
        null=True,
        blank=True,
        help_text="このリマインダーが最後に通知された日付を記録します。重複通知を防止します。"
    )
    
    objects = StudyReminderQuerySet.as_manager() # 時系列の並び替え実現
    
    def __str__(self):
        return f"Reminder(student: {self.student.username}, {self.day_of_week}, {self.time_of_day})"

    def can_be_accessed_by(self, user):
        """
        ユーザーがこのリマインダーにアクセスできるかを判定する。

        実際の判定ロジックは StudyReminderQuerySet.filter_by_access に集約し、
        ここでは「その QuerySet 内に self が含まれているか？」だけを見る。
        （＝アクセス制御ロジックを一箇所にまとめる）
        """
        return StudyReminder.objects.filter_by_access(user).filter(pk=self.pk).exists()

    def send_notification(self):
        """
        Pub/Subトピックにリマインダー情報を送信します（必要な情報のみを送る）。
        """
        logger.info(
            "Sending notification for student: %s, LINE ID: %s",
            self.student.username,
            self.student.line_user_id,
        )

        if not self.student.line_user_id:
            logger.warning("通知に必要なLINE IDの情報が不足しています。")
            return False

        # 1. 送信先チャネルを解決
        line_channel = self.resolve_line_channel()
        if not line_channel:
            logger.error(
                "send_notification: no LineChannel resolved for student %s (org=%s)",
                self.student.id,
                getattr(self.student.organization, "id", None),
            )
            return False

        # 2. チャンネルアクセストークンを封筒復号で取得
        try:
            access_token_bytes = get_secret(line_channel, KeyKind.ACCESS_TOKEN)
            access_token = access_token_bytes.decode("utf-8")
        except Exception as e:
            logger.exception(
                "Failed to decrypt LINE access token for LineChannel %s: %s",
                line_channel.id,
                e,
            )
            return False

        # 3. メッセージ本文生成（従来通り）
        chat_processor = ChatProcessor(self.student)
        message_content = MessageService.generate_message(self, chat_processor)

        # 4. Pub/Sub に送る attributes を構築
        attributes = {
            "line_user_id": self.student.line_user_id,
            "custom_message": self.custom_message or message_content,
            "access_token": access_token,  # ★ ここがマルチチャンネル対応の肝
        }

        # アクセストークンのマスク
        safe_attributes = dict(attributes)
        token = safe_attributes.get("access_token")
        if token:
            safe_attributes["access_token"] = token[:8] + "..."
        logger.info("Publishing message to Pub/Sub (masked): %s", safe_attributes)
        # PubSubPublisher.publish("reminder-topic", "", attributes)
        PubSubPublisher.publish(settings.PUBSUB_REMINDER_TOPIC, "", attributes)
        return True


    def resolve_line_channel(self) -> LineChannel | None:
        """
        このリマインダーの送信に使用する LineChannel を解決する。

        優先順位:
        1. （将来用）リマインダーに明示的に紐付いたチャネルがあればそれを使う
        2. 生徒の所属組織に紐付いた is_active=True のチャネルを1件取得
        """
        # 将来 line_channel フィールドを追加したらここで優先的に見る想定
        # if hasattr(self, "line_channel") and self.line_channel and self.line_channel.is_active:
        #     return self.line_channel

        student = self.student
        org = getattr(student, "organization", None)
        if not org:
            logger.warning(
                "StudyReminder.resolve_line_channel: student %s has no organization",
                student.id,
            )
            return None

        line_channel = org.line_channels.filter(is_active=True).first()
        if not line_channel:
            logger.warning(
                "StudyReminder.resolve_line_channel: no active LineChannel found for organization %s",
                org.id,
            )
            return None

        return line_channel