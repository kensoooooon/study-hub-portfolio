from django.contrib import admin
from .models import LineChannel, LineChannelKeyBundle, KeyKind

@admin.register(LineChannel)
class LineChannelAdmin(admin.ModelAdmin):
    list_display = ("organization", "bot_user_id", "channel_id", "is_active", "updated_at")
    list_filter = ("organization", "is_active")
    search_fields = ("bot_user_id", "channel_id")

@admin.register(LineChannelKeyBundle)
class LineChannelKeyBundleAdmin(admin.ModelAdmin):
    list_display = ("line_channel", "kind", "is_active", "rotated_at", "created_at")
    list_filter = ("kind", "is_active")
    readonly_fields = ("secret_ciphertext", "secret_nonce", "secret_wrapped_dek")
    # Binaryは**表示しない**（readonlyでフォーム非表示、list_displayにも入れない）
