# text_scheduler/services/feasibility.py
from datetime import date, timedelta
from math import ceil
from typing import Iterable, Optional, Dict, Any


def estimate_review_lead_days(required_reviews: int, ef: float = 2.5) -> int:
    """
    最終復習までに必要な“リード日数”の概算を返す。
    想定間隔:
    1回目=+1日, 2回目=+6日, 以降は直前間隔×EF(丸め) を累積。
    ※日次プラン本番ロジックと一致させたい場合は、そちらの係数・丸めに合わせて調整。
    """
    if required_reviews <= 0:
        return 0
    # 1回目, 2回目
    intervals = []
    if required_reviews >= 1:
        intervals.append(1)
    if required_reviews >= 2:
        intervals.append(6)
    # 3回目以降
    prev = intervals[-1] if intervals else 1
    for _ in range(max(0, required_reviews - 2)):
        prev = max(1, int(round(prev * ef)))
        intervals.append(prev)
    return sum(intervals)


def _count_effective_days(start: date, end: date, buffer_weekdays: Optional[Iterable[int]] = None) -> int:
    """
    start..end の“有効学習日”を数える（両端含む）。
    buffer_weekdays: 0=Mon .. 6=Sun を除外したい曜日の反復可能イテラブル。None/空なら全日有効。
    """
    if end < start:
        return 0
    if not buffer_weekdays:
        # 全日有効
        return (end - start).days + 1
    excluded = set(int(x) for x in buffer_weekdays)
    d = start
    cnt = 0
    while d <= end:
        if d.weekday() not in excluded:
            cnt += 1
        d += timedelta(days=1)
    return cnt


def _extend_until_capacity(total_units: int, start_date: date, goal_date: date, cap_new_per_day: int, buffer_weekdays: Optional[Iterable[int]]) -> tuple[int, date]:
    """
    開始日を固定したまま、目標日以降に何営業日延長すれば total_units を cap_new_per_day で捌けるかを見積る。
    戻り値: (slip_days, projected_finish_date)
    """
    # 目標日までに消化できる最大量（予備日除外の“営業日”×cap）
    effective_days = _count_effective_days(start_date, goal_date, buffer_weekdays=buffer_weekdays)
    daily_cap = max(cap_new_per_day, 1)  # cap=0 でも無限遅延を避けるため1で丸め
    already_cover = effective_days * daily_cap

    if already_cover >= total_units:
        return 0, goal_date

    remaining = total_units - already_cover
    slip = 0
    cur = goal_date
    covered = 0
    excluded = set(int(x) for x in (buffer_weekdays or []))
    # 目標日翌日から営業日のみで埋める
    while covered < remaining:
        cur += timedelta(days=1)
        if cur.weekday() in excluded:
            continue
        covered += daily_cap
        slip += 1
        if slip > 3650:  # セーフティブレーク（10年）
            break
    return slip, cur

def diagnose_plan(
    start_date: date,
    goal_date: date,
    unit_start: int,
    unit_end: int,
    est_minutes_per_unit: int,
    daily_minutes_budget: int,
    *,
    # 追加パラメータ（任意）——指定がなければ旧来ロジックに自動フォールバック
    required_reviews: Optional[int] = None,
    ef: float = 2.5,
    buffer_weekdays: Optional[Iterable[int]] = None,  # 例: [5, 6] で土日を除外
    include_timeline: bool = False
) -> Dict[str, Any]:
    """
    フォーム用の妥当性診断API（副作用なし）。
    - 従来: 復習無視で 必要新規/日 と 予算上限/日 を比較
    - 拡張: required_reviews を指定すると「最終復習が目標日に収まる」ための“初回学習締切”を導入し、
            その締切までの有効学習日で均等割りした 必要新規/日 を再計算する。
    戻り値はUIでの表示素材（メッセージ、簡易カレンダー等）。
    """
    # --- 基本集計 ---
    total_units = max(0, unit_end - unit_start + 1)
    total_days_all = max(0, (goal_date - start_date).days + 1)

    # 従来の「復習無視の必要新規/日」
    req_new_per_day_naive = (
        ceil(total_units / max(1, total_days_all)) if total_days_all > 0 else total_units
    )

    # 予算上限（当日復習0前提の暫定上限）
    cap_new_per_day = max(0, daily_minutes_budget // max(1, est_minutes_per_unit))

    # --- ここから拡張：最終復習まで考慮 ---
    use_review_constraint = (required_reviews is not None) and (required_reviews > 0)
    review_lead_days = estimate_review_lead_days(required_reviews, ef) if use_review_constraint else 0
    first_deadline = None
    effective_days_to_deadline = total_days_all  # フォールバック（復習無視）

    if use_review_constraint:
        # 「最終復習が goal_date に収まる」ための“初回学習の締切”
        first_deadline = goal_date - timedelta(days=review_lead_days)
        # 締切までの“有効学習日”を数える（予備日除外を考慮）
        effective_days_to_deadline = _count_effective_days(
            start_date, first_deadline, buffer_weekdays=buffer_weekdays
        )

    # 「締切までに初回学習を終える」ための 必要新規/日（最終版）
    if use_review_constraint:
        if effective_days_to_deadline <= 0:
            # 事実上、開始時点ですでに締切を過ぎている
            req_new_per_day_final = total_units
        else:
            req_new_per_day_final = ceil(total_units / effective_days_to_deadline)
    else:
        # 互換：従来の値をそのまま
        req_new_per_day_final = req_new_per_day_naive

    # ステータス判定
    status = "ok"
    if cap_new_per_day == 0:
        status = "impossible"
    elif cap_new_per_day < req_new_per_day_final:
        # 期日内に“最終復習まで”収めるには新規/日が不足
        status = "tight"

    # --- 簡易カレンダー作成 ---
    schedule = []
    remain = total_units
    current = start_date

    # 新規を割り当てる最終日（復習考慮あり：first_deadline、なし：goal_date）
    last_new_day = first_deadline if use_review_constraint else goal_date

    # last_new_day が start_date より前のケース（既に締切超過）でも
    # ループはスキップされ、remain は total_units のままになる
    while current <= goal_date and remain > 0:
        if current <= (last_new_day or goal_date):
            today_new = min(remain, cap_new_per_day or 0)
        else:
            today_new = 0  # 締切以降は新規を入れない（見通し用）
        schedule.append({
            "date": current.isoformat(),
            "new": int(today_new),
            "review": 0,  # プレビューでは復習を描かず、見通しに徹する
        })
        remain -= today_new
        current += timedelta(days=1)

    # 遅延見込み（従来互換: remain を cap_new_per_day で日割り）
    delay_days = 0
    if remain > 0 and cap_new_per_day > 0:
        delay_days = ceil(remain / cap_new_per_day)
    elif remain > 0 and cap_new_per_day == 0:
        delay_days = None

    # 返却データ
    result: Dict[str, Any] = {
        "total_units": total_units,
        "days": total_days_all,
        "req_new_per_day_naive": req_new_per_day_naive,  # 従来の（復習無視）
        "req_new_per_day": req_new_per_day_final,        # 最終版（復習考慮）
        "cap_new_per_day": cap_new_per_day,
        "status": status,        # ok / tight / impossible
        "delay_days": delay_days,  # 従来互換（表示の補助用）
        "schedule": schedule,    # カレンダー素材（見通し）
        "review_lead_days": review_lead_days,
    }
    # === ここから UX 改善: 「遡る初回締切は表示しない」 ===
    if use_review_constraint:
        deadline_past = first_deadline < start_date  # 締切が開始日より前か
        result["deadline_past"] = deadline_past
        result["backdated_first_deadline"] = first_deadline.isoformat()  # ログ/デバッグ用（UIで使わない）
        if deadline_past:
            # 開始日固定で、目標日以降どれだけ延ばせば cap で捌けるか
            slip_days, projected_finish = _extend_until_capacity(
                total_units=total_units,
                start_date=start_date,
                goal_date=goal_date,
                cap_new_per_day=cap_new_per_day,
                buffer_weekdays=buffer_weekdays,
            )
            result["first_deadline"] = None  # UIには出さない
            result["slip_days"] = slip_days
            result["projected_finish_date"] = projected_finish.isoformat()
        else:
            # 通常ケース：初回締切をそのまま返す
            result["first_deadline"] = first_deadline.isoformat()
            result["effective_days_to_deadline"] = effective_days_to_deadline
            # slip は 0 とみなす（遅延表示は従来の delay_days を補助に）
            result["slip_days"] = 0
            result["projected_finish_date"] = goal_date.isoformat()
    else:
        # 従来互換（復習制約なし）
        result["deadline_past"] = False
        result["backdated_first_deadline"] = None
        result["first_deadline"] = None
        result["slip_days"] = 0
        result["projected_finish_date"] = goal_date.isoformat()

    # ★ ここから追加：詳細タイムラインを要求されたときだけ付ける
    if include_timeline and use_review_constraint and required_reviews > 0:
        last_new_day = first_deadline or goal_date
        result["timeline"] = _build_timeline_with_reviews(
            start_date, goal_date, last_new_day,
            total_units, cap_new_per_day,
            required_reviews, ef,
        )
        result["rounds"] = required_reviews  # JSが列数を決める用
    return result

# text_scheduler/services/feasibility.py（抜粋：関数末尾の直前に追記）
def _build_timeline_with_reviews(
    start_date: date,
    goal_date: date,
    last_new_day: date,
    total_units: int,
    cap_new_per_day: int,
    required_reviews: int,
    ef: float,
) -> list[dict]:
    """
    新規配分（last_new_dayまで）→ 各新規の復習日を間隔 [1,6, round*ef...] で積み上げ、
    日付ごとに {date, new, r1..rn, review_total, overrun_new, overrun_review} を返す。
    ※ここは“見通し用”なので、日次予算の残り時間での再配分まではしない簡易版。
    """
    # 復習間隔の配列
    intervals = []
    if required_reviews >= 1:
        intervals.append(1)
    if required_reviews >= 2:
        intervals.append(6)
    prev = intervals[-1] if intervals else 1
    for _ in range(max(0, required_reviews - 2)):
        prev = max(1, int(round(prev * ef)))
        intervals.append(prev)

    # 1) 日ごと新規を cap_new_per_day で敷き詰め（last_new_dayまで）
    daily_new: dict[date, int] = {}
    remain = total_units
    d = start_date
    while d <= last_new_day and remain > 0:
        n = min(remain, cap_new_per_day or 0)
        daily_new[d] = n
        remain -= n
        d += timedelta(days=1)

    # 1.5) まだ残っている分は、締切を過ぎても「はみ出し」配分する
    # cap_new_per_day が 0 の場合は無限ループを避けて配分を諦める（表は 0 のまま＝不可能）
    if remain > 0 and (cap_new_per_day or 0) > 0:
        d = max(last_new_day + timedelta(days=1), start_date)
        while remain > 0:
            n = min(remain, cap_new_per_day)
            daily_new[d] = daily_new.get(d, 0) + n
            remain -= n
            d += timedelta(days=1)
        spill_last_day = d - timedelta(days=1)
    else:
        spill_last_day = last_new_day

    # 2) 各日の新規 n を「n個のアイテム」とみなし、各interval日に復習が発生するとして積み上げ
    r_maps: list[dict[date, int]] = [dict() for _ in range(len(intervals))]  # r1, r2, ...
    for day, n in daily_new.items():
        for idx, gap in enumerate(intervals):
            due = day + timedelta(days=gap)
            r_maps[idx][due] = r_maps[idx].get(due, 0) + n

    # 3) 表示レンジを start_date..max(goal_date, 配分最終日+最後の間隔) まで
    end_for_view = max(goal_date, spill_last_day)
    if intervals:
        end_for_view = max(end_for_view, spill_last_day + timedelta(days=intervals[-1]))

    # 4) タイムライン行を構築
    rows = []
    cur = start_date
    while cur <= end_for_view:
        row = {
            "date": cur.isoformat(),
            "new": int(daily_new.get(cur, 0)),
            "overrun_new": bool(cur > last_new_day),     # 初回締切を超えた新規
            "overrun_review": False,                      # 初期値
        }
        review_total = 0
        for i, rmap in enumerate(r_maps, start=1):
            cnt = int(rmap.get(cur, 0))
            row[f"r{i}"] = cnt
            review_total += cnt
            if cur > goal_date and cnt > 0:
                row["overrun_review"] = True
        row["review_total"] = review_total
        rows.append(row)
        cur += timedelta(days=1)
    return rows
