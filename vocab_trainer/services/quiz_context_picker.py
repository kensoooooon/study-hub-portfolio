"""
クイズ生成に必要なStudentContextProgressをランダム、あるいは特定割合で選ぶための関数群
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, List, TypeVar
import random
import logging


from django.db.models import Exists, OuterRef, QuerySet


from vocab_trainer.models import WordMeaningContext, StudentContextProgress
from accounts.models import Student
from vocab_trainer.services import get_review_candidates_by_due, softmax_permute_contexts_from_progresses


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PickedQuizContext:
    """コンテキストと該当するバケットの組み合わせを格納
    
    Attributes:
        context (WordMeaningContext): 選ばれたコンテキスト
        bucket (str): コンテキストの元となった分類
    """
    context: WordMeaningContext
    bucket: str  # "new" | "high" | "random" | "fallback"

T = TypeVar('T')

def _pick_random_by_count_offset(qs: QuerySet[T]) -> Optional[T]:
    """指定されたクエリセットから、ランダムに1件を取得
    
    Args:
        qs (QuerySet[T]): 取得対象となるクエリセット
        
    Returns:
        (Optional[T]): ランダムに選ばれた1件のクエリ
    
    Note:
        COUNT + OFFSET 方式でランダムに1件取得。
        IndexError（途中削除など）に備えて1回だけリトライ。
    """
    count = qs.count()
    if count == 0:
        return None

    idx = random.randrange(count)
    try:
        return qs[idx]  # OFFSET idx LIMIT 1
    except IndexError:
        count2 = qs.count()
        if count2 == 0:
            return None
        return qs[random.randrange(count2)]


def _draw_bucket_order(ratio: Tuple[int, int, int]) -> List[str]:
    """ratioに基づいてbucketの試行順を生成

    Args:
        ratio (Tuple[int, int, int]): new(未学習), high(復習優先度が高い), random(条件にこだわらない)の割合

    Returns:
        List[str]: new, high, randomがいずれかの順番で格納されたリスト
    
    Notes:
        例: (6,3,1) なら先頭が new/high/random になる確率が 6/10, 3/10, 1/10。
        ただし同じbucketを何度試しても意味が薄いので、出現順でユニーク化する。
    """
    buckets = (["new"] * ratio[0]) + (["high"] * ratio[1]) + (["random"] * ratio[2])
    random.shuffle(buckets)
    seen = set()
    order: List[str] = []
    for b in buckets:
        if b not in seen:
            seen.add(b)
            order.append(b)
    return order


def pick_quiz_context_by_ratio(
    *,
    student,
    base_contexts: QuerySet[WordMeaningContext],  # WordMeaningContext の queryset
    ratio: Tuple[int, int, int] = (6, 3, 1),
    high_top_n: int = 200,  # high bucket の上位Nから抽選（偏り軽減）
) -> Optional[PickedQuizContext]:
    """base_contexts（母集団コンテキスト）から、ratioに従って1問（WordMeaningContext）を返す。


    Args:
        student : 出題対象となる生徒
        base_contexts (QuerySet): WordM
        high_top_n (int, optional): _description_. Defaults to 200.

    Returns:
        Optional[PickedQuizContext]: WordMeaningContextとbucket(分類のペア)
    
    Notes:
        new   : base_contexts の範囲で progress が一度も紐づいていない relation
        high  : base_contexts の progress を review_priority 降順（上位high_top_nから抽選）
        random: base_contexts の progress のうち accuracy_rate>0 から抽選
    """

    # 0件なら即None
    if not base_contexts.exists():
        return None

    order = _draw_bucket_order(ratio)

    # 取得結果は WordMeaningContext に揃える
    # 高頻度で必要になるので select_related は base_contexts 側で入れてもOK
    base_contexts_sr = base_contexts.select_related(
        "relation",
        "relation__english_word",
        "relation__japanese_meaning",
        "chapter",
    )

    def try_pick_new() -> Optional[WordMeaningContext]:
        # relation単位で「base_contexts 内に progress が存在するか」を判定
        # WordMeaningContext には relation_id がある前提（FK: relation）
        progress_exists_for_relation = StudentContextProgress.objects.filter(
            student=student,
            context__in=base_contexts,
            context__relation_id=OuterRef("relation_id"),
        )
        qs = (
            base_contexts_sr
            .annotate(has_progress=Exists(progress_exists_for_relation))
            .filter(has_progress=False)
        )
        return _pick_random_by_count_offset(qs)

    def _progress_in_base():
        return StudentContextProgress.objects.filter(
            student=student,
            context__in=base_contexts,
        ).select_related(
            "context",
            "context__relation",
            "context__relation__english_word",
            "context__relation__japanese_meaning",
            "context__chapter",
        )

    def try_pick_high() -> Optional[WordMeaningContext]:
        qs = _progress_in_base().order_by("-review_priority")
        # 上位Nから抽選（Nが0なら全体）
        if high_top_n and high_top_n > 0:
            qs = qs[:high_top_n]
        p = _pick_random_by_count_offset(qs)
        return p.context if p else None

    def try_pick_random() -> Optional[WordMeaningContext]:
        qs = _progress_in_base().filter(accuracy_rate__gt=0)
        p = _pick_random_by_count_offset(qs)
        return p.context if p else None

    for b in order:
        if b == "new":
            ctx = try_pick_new()
            if ctx:
                return PickedQuizContext(context=ctx, bucket="new")
        elif b == "high":
            ctx = try_pick_high()
            if ctx:
                return PickedQuizContext(context=ctx, bucket="high")
        else:
            ctx = try_pick_random()
            if ctx:
                return PickedQuizContext(context=ctx, bucket="random")

    # 全滅したら母集団から雑に1件（最後の保険）
    fallback = _pick_random_by_count_offset(base_contexts_sr)
    if fallback:
        return PickedQuizContext(context=fallback, bucket="fallback")

    return None


def pick_random_context(*, base_contexts: QuerySet[WordMeaningContext]) -> Optional[PickedQuizContext]:
    """ベースなるクエリセットから、ランダムにpickedを選択する

    Args:
        base_contexts (QuerySet[WordMeaningContext]): ベースのクエリセット

    Returns:
        Optional[PickedQuizContext]: 対象のWordMeaningContext
    """
    ctx = _pick_random_by_count_offset(
        base_contexts.select_related("relation", "relation__english_word", "relation__japanese_meaning")
    )
    if not ctx:
        return None
    return PickedQuizContext(context=ctx, bucket="uniform")


def pick_review_context_by_softmax(student: Student, *, max_candidates: int = 100, scale: float = 1.0) -> Optional[WordMeaningContext]:
    """復習候補(progress)をdue + fallbackで集め、review_priorityをsoftmaxに通してWordMeaningContextを1件選ぶ。

    Args:
        student (Student): 復習を行いたい生徒
        max_candidates (int, optional): 候補の最大数
        scale (float, optional): ソフトマックスを行う際の温度スケール

    Returns:
        Optional[WordMeaningContext]: 復習対象となるWordMeaningContext
    
    Notes:
        scale = 1で通常のソフトマックス法
        scale < 1で確率分布が鋭くなり、より確信的な選択に
        scale > 1で確率分布が緩やかになり、より保守的な選択に
    """
    progresses = get_review_candidates_by_due(student, max_candidates=max_candidates)
    if not progresses:
        logger.info("復習候補が存在しません。 student_id=%s", getattr(student, "id", None))
        return None

    contexts = softmax_permute_contexts_from_progresses(progresses, scale=scale)
    if not contexts:
        logger.warning("softmax の結果が空でした。 student_id=%s", getattr(student, "id", None))
        return None

    return contexts[0]
