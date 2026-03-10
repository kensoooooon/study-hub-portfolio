from django.db import models
from django.utils.timezone import now
from accounts.models import Student
from django.db import transaction


class Conversation(models.Model):
    """
    会話モデル
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='student_conversations')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    last_message_at = models.DateTimeField(blank=True, null=True)

    def is_active(self, threshold_minutes=60):
        """
        指定された時間内に活動しているかをチェック
        """
        if self.ended_at:
            return False
        if not self.last_message_at:
            return True
        elapsed_time = now() - self.last_message_at
        return elapsed_time.total_seconds() < threshold_minutes * 60

    @staticmethod
    @transaction.atomic
    def get_active_conversation(student):
        """
        アクティブな会話を取得。存在しなければ新規作成
        """
        active_conversation = student.student_conversations.filter(ended_at__isnull=True).last()
        if active_conversation and not active_conversation.is_active():
            active_conversation.ended_at = now()
            active_conversation.save()
            active_conversation = None

        if not active_conversation:
            active_conversation = Conversation.objects.create(student=student)
        return active_conversation

    def __str__(self):
        return f"Conversation: {self.student.username or 'Unknown'} - {self.started_at}"


class MessageLog(models.Model):
    """
    会話中のメッセージログ
    """
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='conversation_logs')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_sent_by_user = models.BooleanField(default=True)

    def __str__(self):
        sender = "User" if self.is_sent_by_user else "Assistant"
        return f"[{self.timestamp}] {sender}: {self.message}"


class StudentSummary(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name="summary_cache")
    summary_text = models.TextField()
    last_generated_at = models.DateTimeField(auto_now=True)  # 最終要約生成日時
    last_conversation_count = models.IntegerField(default=0)  # 最終生成時のメッセージ数
    last_message_timestamp = models.DateTimeField(null=True, blank=True)  # 最終生成時の最新メッセージ時刻
    
    def __str__(self):
        return f"{self.student}: {self.summary_text[10]} ({self.last_generated_at})"

    def needs_update(self):
        logs = MessageLog.objects.filter(
            conversation__student=self.student,
            is_sent_by_user=True
        )

        current_count = logs.count()
        latest_message = logs.order_by('-timestamp').first()

        if not latest_message:
            return False  # メッセージがそもそも存在しない場合

        if current_count != self.last_conversation_count:
            return True  # 件数に差異がある（明確な更新）

        if self.last_message_timestamp is None or latest_message.timestamp > self.last_message_timestamp:
            return True  # 件数は同じでも、内容が変更された可能性あり

        return False  # どちらも変化なし
