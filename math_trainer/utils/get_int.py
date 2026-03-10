import logging

logger = logging.getLogger(__name__)

def get_int_from_session(request, key: str, *, min_value: int | None = None, max_value: int | None = None) -> int | None:
    """セッションから安全に整数を取り出すヘルパー関数

    Args:
        request :セッションを含む対象のリクエスト 
        key (str): 取り出したい値のセッション中のキー
        min_value (int | None, optional): 想定される最小の値
        max_value (int | None, optional): 想定される最大の値

    Returns:
        int | None: 取り出された整数。存在しない、条件に合わない場合はNoneが返る
    """
    raw = request.session.get(key, None)
    if raw is None:
        return None

    try:
        value = int(raw)
    except (TypeError, ValueError):
        logger.warning("有効なデータ型ではありません。(key: %s, raw: %r, user_id: %s)", key, raw, getattr(request.user, "id", None))
        return None

    if min_value is not None and value < min_value:
        logger.warning("指定された最小値を下回っています。 (key: %s, value: %s, min: %s, user_id: %s)", key, value, min_value, getattr(request.user, "id", None))
        return None

    if max_value is not None and value > max_value:
        logger.warning("指定された最大値を上回っています。 (key: %s, value: %s, max: %s, user_id: %s)", key, value, max_value, getattr(request.user, "id", None))
        return None

    return value


def get_int_from_post(request, key: str, *, min_value: int | None = None, max_value: int | None = None) -> int | None:
    """POSTからから安全に整数を取り出すヘルパー関数

    Args:
        request: POSTを含む対象のリクエスト 
        key (str): 取り出したい値のセッション中のキー
        min_value (int | None, optional): 想定される最小の値
        max_value (int | None, optional): 想定される最大の値

    Returns:
        int | None: 取り出された整数。存在しない、条件に合わない場合はNoneが返る
    """
    raw = request.POST.get(key, None)
    if raw is None:
        return None

    try:
        value = int(raw)
    except (TypeError, ValueError):
        logger.warning("有効なデータ型ではありません。(key: %s, raw: %r, user_id: %s)", key, raw, getattr(request.user, "id", None))
        return None

    if min_value is not None and value < min_value:
        logger.warning("指定された最小値を下回っています。 (key: %s, value: %s, min: %s, user_id: %s)", key, value, min_value, getattr(request.user, "id", None))
        return None

    if max_value is not None and value > max_value:
        logger.warning("指定された最大値を上回っています。 (key: %s, value: %s, max: %s, user_id: %s)", key, value, max_value, getattr(request.user, "id", None))
        return None

    return value

def get_allowed_int_from_post(request, key: str, *, allowed: set[int]) -> int | None:
    """POSTから取得した整数が許可された値の中に存在しているかを追加でチェックし値を返す

    Args:
        request : 値が含まれたリクエスト
        key (str): 取得したい値
        allowed (set[int]): 許可された値

    Returns:
        int | None: _description_
    """
    value = get_int_from_post(request, key)
    if value not in allowed:
        logger.warning(
            "POST value not allowed. key=%s value=%r allowed=%s user_id=%s",
            key, value, sorted(allowed), getattr(request.user, "id", None)
        )
        return None
    return value


def get_allowed_int_from_session(request, key: str, *, allowed: set[int]) -> int | None:
    """セッションから取得した整数が許可された値の中に存在しているかを追加でチェックし値を返す

    Args:
        request : 値が含まれたリクエスト
        key (str): 取得したい値
        allowed (set[int]): 許可された値

    Returns:
        int | None: _description_
    """
    value = get_int_from_session(request, key)
    if value not in allowed:
        logger.warning(
            "session value not allowed. key=%s value=%r allowed=%s user_id=%s",
            key, value, sorted(allowed), getattr(request.user, "id", None)
        )
        return None
    return value