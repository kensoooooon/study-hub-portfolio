"""
Why:
    vocab_trainerのsoftmax法を用いた並び替えが、read_trainer, listening_trainerにも用いられていた。
    softmax法自体が、vocab_trainer/utils.pyに入っていたが、quiz_utils.pyと役割の境目が曖昧に
    そのため、共通処理ということで、抽象化したsoftmax法のソートをcommon部に配置する
    StudentContextProgressなど、特定のモデルに依存しない処理として扱うこと
"""
from __future__ import annotations

from typing import Sequence, TypeVar, List
import numpy as np
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


def softmax_weighted_permutation(
    items: Sequence[T],
    scores: Sequence[float],
    *,
    scale: float = 1.0,
    max_prob_fallback_threshold: float = 0.99,
) -> List[T]:
    """
    items と scores から softmax 確率を作り、確率に基づいて「重複なしの順列」を返す。

    Args:
        items: 並べ替え対象
        scores: 各 item のスコア（大きいほど選ばれやすい）
        scale: softmax 前のスケール。大きいほど差が強調される
        max_prob_fallback_threshold:
            softmax の最大確率がこの値を超えるほど 1点集中している場合、
            softmax の意味が薄いので一様シャッフルへフォールバックする

    Returns:
        items を確率的に並べ替えたリスト（len(items) と同じ長さ）

    Notes:
        - 数値安定化のため max を引く（exp のオーバーフロー回避）
        - 失敗時は空リストではなく「一様シャッフル」へ寄せても良いが、
            ここでは呼び出し側の期待に合わせやすいように一様シャッフルで返す
    """
    if not items:
        return []

    if len(items) != len(scores):
        raise ValueError("items と scores の長さが一致しません。")

    s = np.asarray(scores, dtype=float)
    if s.size == 0:
        return list(items)

    # NaN / inf を含む場合は安全側に倒す（均等シャッフル）
    if np.any(np.isnan(s)) or np.any(~np.isfinite(s)):
        logger.warning("scores に NaN/inf が含まれます。均等シャッフルへフォールバックします。")
        arr = np.array(list(items), dtype=object)
        return list(np.random.permutation(arr))

    scaled = s * float(scale)
    exp_scores = np.exp(scaled - np.max(scaled))
    total = float(np.sum(exp_scores))

    if total <= 0.0 or np.isnan(total) or not np.isfinite(total):
        logger.warning("softmax 計算に失敗しました。total=%s (scale=%s)", total, scale)
        arr = np.array(list(items), dtype=object)
        return list(np.random.permutation(arr))

    probs = exp_scores / total

    # 1点集中ならソフトマックスの意味が薄いのでフォールバック
    try:
        if float(np.max(probs)) >= float(max_prob_fallback_threshold):
            logger.warning(
                "確率が極端に集中しています(max_prob=%s)。均等シャッフルへフォールバックします。",
                float(np.max(probs)),
            )
            arr = np.array(list(items), dtype=object)
            return list(np.random.permutation(arr))
    except Exception:
        # 念のため
        pass

    try:
        arr = np.array(list(items), dtype=object)
        selected = np.random.choice(arr, size=len(arr), replace=False, p=probs)
        return list(selected)
    except Exception:
        logger.exception("softmax による np.random.choice に失敗しました。均等シャッフルへフォールバックします。")
        arr = np.array(list(items), dtype=object)
        return list(np.random.permutation(arr))
