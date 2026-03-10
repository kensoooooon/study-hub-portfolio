from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'  # 主キーを指定していない場合のidを指定
    name = 'accounts'

    def ready(self):
        # シグナルを登録するために import
        from . import signals  # noqa: F401