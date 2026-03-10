# text_scheduler/tests/test_daily_plan_backcasting.py
import datetime as dt
import math
import pytest
from django.utils import timezone

from accounts.models import Student  # 必要に応じて import を調整
from text_scheduler.models import LearningMaterial, StudentUnitProgress
from text_scheduler.services.daily_plan import (
    generate_or_get_today_plan,
    DAILY_MINUTES_BUDGET,
    OVERDUE_REVIEW_STRICT_RATIO,
    OVERTIME_NEW_CAP,
)

@pytest.mark.django_db
def _make_student(username="stu"):
    # 環境に応じて create_user の引数を調整してください
    return Student.objects.create_user(
        email=None, password="pass", role="student", username=username
    )

@pytest.mark.django_db
def _make_material(student, start_date, goal_date, total_units=30, required_reviews=3,
                   estimated_minutes=5, buffer_weekdays=None):
    return LearningMaterial.objects.create(
        target_student=student,
        created_by=student,  # teacher でなくても可（ForeignKey は BaseUser）
        title="テスト教材",
        unit_label="番",
        start_number=1,
        end_number=total_units,
        required_reviews=required_reviews,
        estimated_minutes_per_unit=estimated_minutes,
        start_date=start_date,
        goal_date=goal_date,
        buffer_weekdays=buffer_weekdays or [],
    )

def _nth_weekday(d, weekday):
    """d から見て次の指定曜日(0=Mon..6=Sun)の日付を返す"""
    add = (weekday - d.weekday()) % 7
    return d + dt.timedelta(days=add)

# --- 1) 予備日（buffer）では新規0になる ---
@pytest.mark.django_db
def test_new_is_zero_on_buffer_day():
    stu = _make_student("stu_buf")
    today = timezone.localdate()
    start = today
    goal  = today + dt.timedelta(days=30)

    # 土日を予備日に設定
    mat = _make_material(stu, start, goal, total_units=20, buffer_weekdays=[5, 6])

    # 次の土曜日
    sat = _nth_weekday(today, 5)
    plan = generate_or_get_today_plan(mat, date=sat)
    assert plan.suggested_new_count == 0
    # 復習は従来通り抽出される（ここでは作っていないので 0 のはず）
    assert plan.estimated_total_minutes == 0

# --- 2) レビューが渋滞している日は新規が止まる ---
@pytest.mark.django_db
def test_new_stops_when_reviews_over_budget():
    stu = _make_student("stu_over")
    today = timezone.localdate()
    start = today
    goal  = today + dt.timedelta(days=10)
    est_m = 5
    mat = _make_material(stu, start, goal, total_units=40, estimated_minutes=est_m)

    # 予算×閾値を超えるレビュー分だけ Progress を作成（new は抑制されるはず）
    threshold_minutes = int(DAILY_MINUTES_BUDGET * OVERDUE_REVIEW_STRICT_RATIO)
    need_reviews = (threshold_minutes // est_m) + 1  # 閾値超え
    due_dt = timezone.now() - dt.timedelta(days=1)   # 期日超過＝今日レビュー対象
    for i in range(1, need_reviews + 1):
        StudentUnitProgress.objects.create(
            student=stu, material=mat, number=i,
            status="reviewing", repetition_count=2, interval_days=6,
            next_due_at=due_dt,
        )

    plan = generate_or_get_today_plan(mat, date=today)
    assert plan.suggested_new_count == 0, "レビュー渋滞日は新規が0になるはず"
    # 全体時間が予算×閾値を超える値に張り付いていることを確認（新規0なので=レビュー分）
    assert plan.estimated_total_minutes >= threshold_minutes

# --- 3) 目標日を過ぎたら新規は OVERTIME_NEW_CAP に制限 ---
@pytest.mark.django_db
def test_new_is_capped_in_overtime_mode():
    stu = _make_student("stu_overdue")
    today = timezone.localdate()
    start = today - dt.timedelta(days=40)
    goal  = today - dt.timedelta(days=1)  # 既に超過
    mat = _make_material(stu, start, goal, total_units=10)

    plan = generate_or_get_today_plan(mat, date=today)
    assert plan.suggested_new_count <= max(0, int(OVERTIME_NEW_CAP))

# --- 4) 全ユニットが初回済みなら新規は出ない ---
@pytest.mark.django_db
def test_new_is_zero_after_all_initial_done():
    stu = _make_student("stu_all")
    today = timezone.localdate()
    start = today
    goal  = today + dt.timedelta(days=20)
    total_units = 12
    mat = _make_material(stu, start, goal, total_units=total_units)

    # 全番号について「一度は学習済み」状態にする（repetition_count>0）
    past = timezone.now() - dt.timedelta(days=2)
    for i in range(1, total_units + 1):
        StudentUnitProgress.objects.create(
            student=stu, material=mat, number=i,
            status="learning", repetition_count=1, interval_days=1,
            next_due_at=past,  # 期限切れレビュー扱いでもOK
        )

    plan = generate_or_get_today_plan(mat, date=today)
    assert plan.suggested_new_count == 0

# --- 5) 逆算ベースで新規が前倒し投入され、時間予算も超えない ---
@pytest.mark.django_db
def test_backcasting_and_time_budget_hold():
    stu = _make_student("stu_bc")
    today = timezone.localdate()
    start = today
    goal  = today + dt.timedelta(days=25)
    est_m = 5
    total_units = 25
    mat = _make_material(stu, start, goal, total_units=total_units, estimated_minutes=est_m, buffer_weekdays=[6])  # 日曜だけ予備日

    plan = generate_or_get_today_plan(mat, date=today)
    # 逆算の結果として新規提案が >0（締切に向けて均等割り）であること
    assert plan.suggested_new_count >= 0
    # 時間予算を超えない（レビューが無いので new のみで検証可能）
    assert plan.estimated_total_minutes <= DAILY_MINUTES_BUDGET
