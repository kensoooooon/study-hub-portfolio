import json
import base64, hmac, hashlib
import logging
from django.http import HttpRequest
from .models import LineChannel, KeyKind
from .services import get_secret

logger = logging.getLogger(__name__)

class SignatureError(Exception): ...
class ChannelNotFound(Exception): ...

def resolve_channel_and_verify(request: HttpRequest) -> LineChannel:
    """
    request.body から destination を抜き出し、該当チャネルの
    CHANNEL_SECRET を封筒復号して署名を検証。OKなら LineChannel を返す。
    """
    logger.debug("resolve_channel_and_verify called", extra={"path": request.path})

    body = request.body
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        logger.exception(
            "Webhookで不正なJSONが入力されました",
            extra={"raw_snippet": repr(body[:200])},
        )
        raise

    dest = payload.get("destination")
    signature = (
        request.headers.get("X-Line-Signature")
        or request.META.get("HTTP_X_LINE_SIGNATURE", "")
    )

    if not dest:
        logger.warning(
            "destinationが指定されていません",
            extra={"raw_snippet": repr(body[:200])},
        )
        raise ChannelNotFound("missing destination")

    try:
        ch = LineChannel.objects.get(bot_user_id=dest, is_active=True)
    except LineChannel.DoesNotExist:
        logger.error(
            "対応するアクティブなLineChannelが見つかりませんでした",
            extra={"destination": dest},
        )
        raise ChannelNotFound(f"LineChannel not found for destination={dest!r}")
    except Exception:
        logger.exception(
            "LineChannel取得処理で予期せぬエラーが発生しました",
            extra={"destination": dest},
        )
        raise

    logger.info(
        "LineChannelを解決しました",
        extra={"channel_id": ch.id, "destination": dest},
    )

    secret = get_secret(ch, KeyKind.CHANNEL_SECRET)  # bytes
    expected = base64.b64encode(hmac.new(secret, body, hashlib.sha256).digest()).decode()

    if not hmac.compare_digest(signature, expected):
        logger.error(
            "不正な署名が検出されました",
            extra={"destination": dest},
        )
        raise SignatureError("invalid signature")

    return ch
