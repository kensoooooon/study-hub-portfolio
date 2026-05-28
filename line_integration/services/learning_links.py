from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse

LEARNING_DESTINATIONS = {
    "student_home":       "student:home",
    "read_textbook":      "read_trainer:quiz_type_select_for_student",
    "read_eiken":         "read_trainer:eiken_quiz_type_select_for_student",
    "listening_textbook": "listening_trainer:quiz_type_select_for_student",
    "listening_eiken":    "listening_trainer:eiken_quiz_type_select_for_student",
}


class InvalidDestination(ValueError):
    pass


def get_learning_path(destination_key: str) -> str:
    """allowlist から reverse() で内部URLパスを返す。"""
    route_name = LEARNING_DESTINATIONS.get(destination_key)
    if not route_name:
        raise InvalidDestination(f"Unknown destination: {destination_key!r}")
    return reverse(route_name)


def get_login_redirect_path(destination_key: str) -> str:
    """
    login?next=<内部パス> の形式でパスを返す。

        - next は allowlist 由来の内部URLのみを使用する。
        - urlencode により / は %2F にエンコードされるが、
            Django の get_redirect_url() では正しく復元される。
            将来 next_path にクエリ文字列が含まれても、
            外側のクエリパラメータと混ざりにくい。
    """
    login_path = reverse("accounts_auth:login")
    next_path = get_learning_path(destination_key)
    return f"{login_path}?{urlencode({'next': next_path})}"


def build_absolute_url(path: str, request=None) -> str:
    """絶対URLを組み立てる。request があれば build_absolute_uri、なければ APP_PUBLIC_BASE_URL を使う。"""
    if request is not None:
        return request.build_absolute_uri(path)
    base = getattr(settings, "APP_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    return f"{base}{path}"


def build_line_message(destination_key: str = "student_home", request=None) -> str:
    """LINE送信用の学習リンク付き文面を返す。"""
    path = get_login_redirect_path(destination_key)
    url = build_absolute_url(path, request)
    return (
        "今日の学習はこちらから始められます。\n"
        "ログイン画面が表示された場合は、いつものアカウントでログインしてください。\n"
        f"{url}"
    )
