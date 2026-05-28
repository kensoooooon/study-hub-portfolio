import numpy as np
from django.utils import timezone

from read_trainer.models import StudentReadingPassageProgress


def get_pruned_progresses(student, source_type, max_count=100):
    """
    指定生徒・教材種別の進捗オブジェクトを取得し、
    max_count を超えていたら古い順に削除してから返却する。
    """
    progresses = StudentReadingPassageProgress.objects.with_active_and_valid_student().filter(
        student=student,
        passage__source_type=source_type,
    ).select_related("passage")

    excess = progresses.count() - max_count
    if excess > 0:
        ids_to_delete = list(
            progresses
            .order_by("last_reviewed_at",  "id")
            .values_list("id", flat=True)[:excess]
        )

        StudentReadingPassageProgress.objects.filter(
            id__in=ids_to_delete  # クエリセットをスライスで一部取得したままでは削除不可なので、取得し直して削除
        ).delete()

        progresses = StudentReadingPassageProgress.objects.with_active_and_valid_student().filter(
            student=student,
            passage__source_type=source_type,
        ).select_related("passage")

    return progresses


def select_passages_for_student(student, source_type="textbook", top_k=10, temperature=1.0, max_progresses=100):
    """
    ソフトマックス法を用いて、復習優先度に応じた確率的な出題を行う。

    高い優先度を持つ問題がより選ばれやすくなる一方で、温度パラメータにより
    出題の多様性や集中度を調整できるようになっている。

    Args:
        student (Student): 対象となる生徒オブジェクト
        source_type (str): 出題元の教材タイプ（例："textbook", "eiken" など）
        top_k (int): 出題する最大件数。復習候補からこの件数分を確率的に選ぶ
        temperature (float): 温度パラメータ。
            - 値が小さいほど「優先度の高い問題に集中」して選ばれる（鋭い分布）
            - 値が大きいほど「全体からまんべんなく」選ばれる（なだらかな分布）
            - 一般に 0.5〜2.0 の間で調整される

    Returns:
        List[StudentReadingPassageProgress]: Softmax に基づいて選ばれた出題対象の進捗オブジェクト群
        True, False: 対象となるパッセージ群が存在するか否か
    
    Notes:
        - temperatureの用途ごとの想定値について
            temperature=0.5 → 高スコアがほぼ必ず選ばれる（集中復習向け
            temperature=1.0 → 優先度に応じたバランスの良い出題（標準）
            temperature=2.0 → 低スコアも選ばれるようになる（ランダム性重視）

    """
    progresses = get_pruned_progresses(student, source_type, max_count=max_progresses)
    has_passages = progresses.exists()

    if not has_passages:
        return [], False

    now = timezone.now()
    scored = [(p, p.get_review_priority(now)) for p in progresses]
    if not scored:
        return [], True  # progressesはあっても priority算出対象がないケース

    scores = np.array([s for _, s in scored])
    scaled = scores / temperature
    probs = np.exp(scaled - np.max(scaled))
    probs /= np.sum(probs)

    chosen = np.random.choice([p for p, _ in scored], size=min(top_k, len(scored)), p=probs, replace=False)
    return list(chosen), True