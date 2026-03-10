from django.contrib import admin
from conversations.models import Conversation


class ConversationInline(admin.TabularInline):
    """
    生徒管理画面でConversationをインライン表示
    """
    model = Conversation
    extra = 0
    readonly_fields = ('started_at', 'ended_at', 'last_message_at')
    show_change_link = True
