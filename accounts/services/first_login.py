from accounts.models import BaseUser

TARGET_ROLES = frozenset({"classroom_administrator", "teacher", "student"})


def requires_first_login_password_change(user: BaseUser) -> bool:
    """初回ログイン扱いで、パスワード変更が必要なユーザーかどうかを判定する

    Args:
        user (BaseUser): 対象となるユーザー

    Returns:
        bool: パスワード変更が必要か否か
    
    Notes:
        - 未ログインユーザーについては、
            - ログイン画面に遷移→初回ログイン扱い→アカウント編集画面へ遷移
            - ログイン画面に遷移→ログイン済み扱い→nextでパラメータorホームページに戻る
        という流れになる。単体ではなく、views, middlewareとの組み合わせで利用される点に注意
    """

    if not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False):
        return False

    if getattr(user, "role", None) not in TARGET_ROLES:
        return False

    return getattr(user, "is_first_login", False)
