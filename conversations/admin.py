from django.contrib import admin
from .models import Conversation, MessageLog


class MessageLogInline(admin.TabularInline):
    """
    Conversationの詳細画面でMessageLogをインライン表示
    """
    model = MessageLog
    extra = 0
    readonly_fields = ('message', 'timestamp', 'is_sent_by_user')
    can_delete = False  # メッセージは削除不可

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs[:50]  # 最大50件のみ表示


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """
    Conversationを管理画面で表示
    """
    list_display = ('student', 'started_at', 'ended_at', 'last_message_at')
    readonly_fields = ('student', 'started_at', 'ended_at', 'last_message_at')
    search_fields = ('student__username', 'student__email', 'student__line_user_id')
    list_filter = ('ended_at',)
    inlines = [MessageLogInline]
