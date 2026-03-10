import logging


from vocab_trainer.models import StudentContextProgress, WordMeaningContext
from common.weighted_sampling import softmax_weighted_permutation


logger = logging.getLogger(__name__)


def softmax_permute_contexts_from_progresses(
    progresses_with_priority: list[StudentContextProgress],
    *,
    scale: float = 1.0,
) -> list[WordMeaningContext]:
    """
    StudentContextProgress の review_priority をスコアとして softmax を計算し、
    context（WordMeaningContext）を確率的に並べ替えて返す。

    Args:
        progresses_with_priority: 対象生徒の学習進捗（select_related("context") 推奨）
        scale: softmax 前スケール

    Returns:
        list[WordMeaningContext]: context を確率的に並べ替えたリスト
    """
    if not progresses_with_priority:
        logger.warning("出題候補が存在しません。")
        return []

    # Django モデル依存はここに閉じ込める
    contexts = [p.context for p in progresses_with_priority]
    scores = [float(p.review_priority) for p in progresses_with_priority]

    # common の抽象関数を呼ぶ
    selected_contexts = softmax_weighted_permutation(
        contexts,
        scores,
        scale=scale,
    )

    # ログは最小情報（必要なら）
    if selected_contexts:
        logger.debug(
            "softmax selected_context[0] id=%s",
            getattr(selected_contexts[0], "id", None),
        )
    return selected_contexts


def softmax_sort_progresses(
    progresses_with_priority: list[StudentContextProgress],
    scale: float = 1.0,
) -> list[WordMeaningContext]:
    """
    互換用（既存コードのために残す）。

    ※戻り値は StudentContextProgress ではなく WordMeaningContext のリストです。
    """
    return softmax_permute_contexts_from_progresses(progresses_with_priority, scale=scale)
