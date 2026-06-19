from django.conf import settings
from django.urls import reverse

from accounts.services.first_login import requires_first_login_password_change


def _get_allowed_paths() -> set[str]:
    """
    ミドルウェアの処理の例外となるパスを返す
    """
    return {
        reverse("accounts_auth:login"),
        reverse("accounts_auth:logout"),
        reverse("organization_admin:account_edit"),
    }


class FirstLoginMiddleware:
    """
    初回ログイン扱いで、初期パスワード変更処理が必要なアクセスを判別し、アカウント編集へ誘導する
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if requires_first_login_password_change(request.user):
            path = request.path
            allowed_prefixes = (
                settings.STATIC_URL,
                f"{settings.MEDIA_URL}temp_audio/",
            )
            if path not in _get_allowed_paths() and not any(
                path.startswith(p) for p in allowed_prefixes
            ):
                from django.shortcuts import redirect
                return redirect(reverse("organization_admin:account_edit"))
        return self.get_response(request)
