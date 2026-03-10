# text_scheduler/services/daily_plan.py
"""
“逆算型”の当日プラン生成（過剰集中の抑制＆期日超過モードを含む）

設計方針：
- 逆算：goal_date に対して、最後の新規投入分の“最終復習”が期間内に収まるように
  初回学習の締切 = goal_date - review_lead_days を設定し、今日〜締切の“有効学習日”
  （予備日を除く）で残ユニットを均等割り（天井）して新規件数を決定。
- 復習：next_due_at <= 今日 の番号を古い順に提示。
- 過剰集中抑制（A/B）：
  A) 日次の時間予算（DAILY_MINUTES_BUDGET 分）内に収まるよう、新規を時間で上限化。
  B) レビュー渋滞日（レビュー時間が予算の閾値比を超過）は、新規を自動停止。
- 期日超過モード：
  today > goal_date の場合は“超過モード”。原則レビュー優先で新規は最小限/停止（ポリシー選択）。

セキュリティ/堅牢性：
- 生成は transaction.atomic + select_for_update。
- goal_date / start_date 欠損時は安全フォールバック（固定上限）で UI を止めない。
- 各所にCAP（MAX_...）を設置し、異常負荷提案を抑制。
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List
from django.utils import timezone
from django.db import transaction
from datetime import date, timedelta
import math

from text_scheduler.models import (
    LearningMaterial, DailyPlan, StudentUnitProgress
)

# ===== DTO =====
@dataclass(frozen=True)
class TodayPlanDTO:
    """
    その日にやるべき内容をピックアップするコンテナ
    
    Attributes:
        new_count (int): 新規に学習要件
        review_numbers (list[int]): 復習すべき問題番号
        estimated_total_minutes (int): 想定される学習時間
    """
    new_count: int
    review_numbers: list[int]
    estimated_total_minutes: int

# ===== チューニング用定数 =====
DEFAULT_DAILY_NEW = 3             # フォールバック時の新規件数（安全）
DEFAULT_EASE_FACTOR = 2.5         # SM-2 初期EF
MAX_NEW_CAP_PER_DAY = 20          # 新規の絶対上限（異常防止）
MAX_DUE_REVIEWS_PER_DAY = 200     # 復習候補の抽出上限（クエリ/UX安全弁）

# --- 過剰集中の抑制（時間予算ベース） ---
DEFAULT_DAILY_MINUTES_BUDGET = 45         # 1日の学習時間予算（分）
OVERDUE_REVIEW_STRICT_RATIO = 1.2 # レビューが予算の x 倍を超えたら新規停止

# --- 期日超過モードのポリシー ---
# 0: 完全停止（新規0）/ 1: 最小限（1件まで）/ N: 上限N件まで
OVERTIME_NEW_CAP = 1

# ===== ヘルパ =====
def _resolve_budget(material) -> int:
    # 教材側 > 生徒側(将来) > 既定 の優先順
    return getattr(material, "daily_minutes_budget", None) or DEFAULT_DAILY_MINUTES_BUDGET

def _is_buffer_day(material: LearningMaterial, d: date) -> bool:
    """
    ある曜日が予備日になっているか否か
    
    Args:
        material (LearningMaterial): 対象教材
        d (date): 対象曜日
    """
    w = material.buffer_weekdays or []
    return d.weekday() in set(w)

def _remaining_new_count(material: LearningMaterial) -> int:
    """残っている新規学習件数の算出

    Args:
        material (LearningMaterial): 対象教材

    Returns:
        int: 残りの新規学習すべき件数
    """
    start, end = material.start_number, material.end_number
    total = end - start + 1
    learned = (
        StudentUnitProgress.objects
        .filter(material=material, repetition_count__gt=0, student_id=material.target_student_id)
        .values_list("number", flat=True)
        .distinct().count()
    )
    return max(0, total - learned)

def _due_review_numbers(material: LearningMaterial, d: date) -> list[int]:
    """
    その日に復習すべき(すでに復習予定が来ている)候補を上限付きで返す
    
    Args:
        material (LearningMaterial): 対象教材
        d (date): 判定に用いる日付
    """
    qs = (
        StudentUnitProgress.objects
        .filter(material=material, next_due_at__isnull=False, next_due_at__date__lte=d, student_id=material.target_student_id)
        .order_by("next_due_at", "number")
        .values_list("number", flat=True)
    )
    return list(qs[:MAX_DUE_REVIEWS_PER_DAY])

def _estimate_review_lead_days(required_reviews: int, ef: float = DEFAULT_EASE_FACTOR) -> int:
    """
    初回から最後の復習までにかかると見積もられる日数を保守的に計算する関数

    Args:
        required_reviews(int): 必要復習回数
        ef (float): sm-2型の計算において、記憶の減衰に用いられる定数。大きいほど記憶の減衰を大きいとみなす
    
    Developing:
        初回から最終復習までの“必要リード日数”を保守的に見積もる（SM-2初期挙動）。
        rep=0(初回) -> +1日 -> +6日 -> 以降 round(prev * EF)
        例）required_reviews=3: 1 + 6 + round(6*EF) ≒ 22日（EF=2.5想定）
    """
    if required_reviews <= 0:
        return 0
    intervals: List[int] = []
    if required_reviews >= 1:
        intervals.append(1)
    if required_reviews >= 2:
        intervals.append(6)
    prev = intervals[-1] if intervals else 1
    for _ in range(max(0, required_reviews - 2)):
        nxt = max(1, int(round(prev * ef)))
        intervals.append(nxt)
        prev = nxt
    return int(sum(intervals))

def _count_effective_learning_days(material: LearningMaterial, start_d: date, end_d: date) -> int:
    """
    start_d〜end_d（含む）で、予備日を除いた“初回学習に使える日数”を数える。
    
    Args:
        material(LearningMaterial): 対象教材
        start_d (date): 学習開始日
        end_d (date): 学習終了日
    """
    if end_d < start_d:
        return 0
    cnt = 0
    cur = start_d
    while cur <= end_d:
        if not _is_buffer_day(material, cur):
            cnt += 1
        cur += timedelta(days=1)
    return cnt

def _compute_new_count_by_backcasting(material: LearningMaterial, today: date) -> int:
    """
    逆算で当日の新規件数を決定。
        1) review_lead_days を見積もる
        2) 初回締切 = goal_date - review_lead_days
        3) 今日〜締切の“有効学習日”（予備日除外）を数える
        4) 残ユニット / 有効日数 を天井して新規件数に採用
    """
    remaining_units = _remaining_new_count(material)
    if remaining_units <= 0:
        return 0

    goal = material.goal_date
    start = material.start_date
    if not goal or not start:
        # goal/start 不在はフォールバック
        return min(DEFAULT_DAILY_NEW, remaining_units)

    required_reviews = int(material.required_reviews or 0)
    review_lead_days = _estimate_review_lead_days(required_reviews, ef=DEFAULT_EASE_FACTOR)
    last_first_learn_deadline = goal - timedelta(days=review_lead_days)

    # 既に締切を超過 → 可能な範囲で押し込み（CAP付き）
    if today > last_first_learn_deadline:
        return min(MAX_NEW_CAP_PER_DAY, remaining_units)

    # 締切までの“有効学習日”
    effective_days = _count_effective_learning_days(material, today, last_first_learn_deadline)
    if effective_days <= 0:
        return min(MAX_NEW_CAP_PER_DAY, remaining_units)

    if _is_buffer_day(material, today):
        return 0

    per_day = int(math.ceil(remaining_units / effective_days))
    return max(0, min(per_day, MAX_NEW_CAP_PER_DAY, remaining_units))

# ===== メイン =====
@transaction.atomic
def generate_or_get_today_plan(material: LearningMaterial, date=None) -> DailyPlan:
    """
    “逆算型 + 過剰集中抑制 + 期日超過モード”で当日の学習プランを生成/更新。
    - 新規：逆算により件数を算出し、さらに時間予算で上限化（レビュー渋滞日は停止）。
    - 復習：next_due_at <= 今日 を古い順に提示。
    """
    today = date or timezone.localdate()
    plan, _ = DailyPlan.objects.select_for_update().get_or_create(
        student=material.target_student,
        material=material,
        date=today,
        defaults={"suggested_new_count": 0, "suggested_review_numbers": [], "estimated_total_minutes": 0},
    )

    # 1) 逆算で新規件数の“候補”を出す
    new_count = _compute_new_count_by_backcasting(material, today)

    # 2) 復習は従来通り抽出（古い順）。上限はクエリ側でカット済み。
    review_numbers = _due_review_numbers(material, today)

    # 3) 時間予算で新規を上限化（A）
    est_per_unit = int(material.estimated_minutes_per_unit or 5)
    est_per_unit = max(1, min(est_per_unit, 240))  # 異常値ガード
    review_minutes = len(review_numbers) * est_per_unit
    remaining_minutes = max(0, _resolve_budget(material) - review_minutes)
    max_new_by_time = remaining_minutes // est_per_unit
    new_count = max(0, min(new_count, max_new_by_time))

    # 4) レビュー渋滞日の新規停止（B）
    if review_minutes > int(_resolve_budget(material) * OVERDUE_REVIEW_STRICT_RATIO):
        new_count = 0

    # 5) 期日超過モード（goal_date を過ぎたらレビュー優先）
    if material.goal_date and today > material.goal_date:
        cap = max(0, int(OVERTIME_NEW_CAP))
        new_count = min(new_count, cap)

    # 6) 見積り（新規 + 復習）
    est_minutes = (new_count + len(review_numbers)) * est_per_unit

    # 7) 保存
    plan.suggested_new_count = int(new_count)
    plan.suggested_review_numbers = list(review_numbers)
    plan.estimated_total_minutes = int(est_minutes)
    plan.full_clean()
    plan.save(update_fields=["suggested_new_count", "suggested_review_numbers", "estimated_total_minutes"])
    return plan

def build_dto(plan: DailyPlan) -> TodayPlanDTO:
    return TodayPlanDTO(
        new_count=plan.suggested_new_count,
        review_numbers=list(plan.suggested_review_numbers or []),
        estimated_total_minutes=plan.estimated_total_minutes,
    )
