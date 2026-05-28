from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

def get_and_validate_batch_id_from_request(request) -> int:
    """リクエストからバリデーションされたバッチIDを取得する

    Args:
        request: バッチIDが含まれていると想定されるリクエスト

    Raises:
        ValidationError: バッチIDがリクエストに含まれていなかったとき
        ValidationError: バッチIDが整数として解釈できなかったとき
        ValidationError: バッチIDが0以下の値になっていたとき

    Returns:
        batch_id (int): 値として正しいことが保証されたバッチID
    """
    batch_id_raw = request.POST.get("batch_id") or request.GET.get("batch_id")

    if not batch_id_raw:
        logger.warning("バッチIDが送信されていません。(batch_id=%s)", batch_id_raw)
        raise ValidationError("バッチIDが不正です。")

    try:
        batch_id = int(batch_id_raw)
    except (ValueError, TypeError):
        logger.warning(
            "バッチIDの値もしくは型のエラー(batch_id=%s, type=%s)",
            batch_id_raw,
            type(batch_id_raw),
        )
        raise ValidationError("バッチIDが不正です。")

    if batch_id <= 0:
        logger.warning("バッチIDの値が0以下です。(batch_id=%s)", batch_id_raw)
        raise ValidationError("バッチIDが不正です。")

    return batch_id
