from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.urls import reverse
import logging

from accounts.services.first_login import requires_first_login_password_change

logger = logging.getLogger(__name__)



def _get_allowed_paths() -> set[str]:
    """
    ミドルウェアの処理の例外となるパスを返す
    """
    return {
        reverse("accounts_auth:login"),
        reverse("accounts_auth:logout"),
        reverse("organization_admin:account_edit"),
    }


class RejectSuperuserMiddleware:
    """is_superuser のユーザーによるアクセスを一律拒否する (Issue #162)。

    生成ガード + BaseUser.Meta の CheckConstraint により is_superuser=True の
    ユーザーは本来存在し得ないが、制約導入前に発行された認証済みセッション等が
    残っていた場合の境界防御。redirect ではなく PermissionDenied を送出する
    (リダイレクトループ回避、get_success_url と同方針)。ログアウトは通し、
    詰まないようにする。AuthenticationMiddleware の直後に配置すること。
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def _get_allowed_paths(self) -> set[str]:
        return {
            reverse("accounts_auth:login"),
            reverse("accounts_auth:logout"),
        }

    def __call__(self, request):
        user = getattr(request, "user", None)

        if user is None:
            logger.warning("userオブジェクトが取得できていません。ミドルウェア順序を確認して下さい。")
            return self.get_response(request)

        if user.is_authenticated and user.is_superuser:
            path = request.path
            allowed_prefixes = tuple(
                p for p in (settings.STATIC_URL, settings.MEDIA_URL) if p
            )
            if path not in self._get_allowed_paths() and not any(
                path.startswith(p) for p in allowed_prefixes
            ):
                raise PermissionDenied("このアカウントではアクセスできません。")
        return self.get_response(request)


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
