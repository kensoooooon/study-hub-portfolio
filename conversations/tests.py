from django.test import TestCase
from .models import Conversation, MessageLog
from accounts.models import Student


class ConversationModelTest(TestCase):
    def test_create_active_conversation(self):
        """
        新規アクティブ会話を作成するテスト
        """
        student = Student.objects.create(username="testuser", email="testuser@example.com")
        conversation = Conversation.get_active_conversation(student)
        self.assertIsNotNone(conversation)
        self.assertEqual(conversation.student, student)

    def test_get_existing_active_conversation(self):
        """
        既存のアクティブな会話を取得するテスト
        """
        student = Student.objects.create(username="testuser", email="testuser@example.com")
        # 既存の会話を作成
        Conversation.objects.create(student=student)
        active_conversation = Conversation.get_active_conversation(student)
        self.assertEqual(active_conversation.student, student)
        self.assertIsNone(active_conversation.ended_at)

    def test_create_new_conversation_after_inactive(self):
        """
        非アクティブな会話後に新しい会話を作成するテスト
        """
        student = Student.objects.create(username="testuser", email="testuser@example.com")
        # 非アクティブな会話を作成
        old_conversation = Conversation.objects.create(student=student, ended_at="2025-01-01T00:00:00Z")
        new_conversation = Conversation.get_active_conversation(student)
        self.assertNotEqual(old_conversation, new_conversation)
        self.assertIsNone(new_conversation.ended_at)

    def test_message_log_creation(self):
        """
        メッセージログが正しく作成されるかをテスト
        """
        student = Student.objects.create(username="testuser", email="testuser@example.com")
        conversation = Conversation.get_active_conversation(student)
        message_log = MessageLog.objects.create(conversation=conversation, message="Hello", is_sent_by_user=True)

        self.assertEqual(message_log.conversation, conversation)
        self.assertEqual(message_log.message, "Hello")
        self.assertTrue(message_log.is_sent_by_user)
