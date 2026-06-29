import datetime as dt
import math
from django.test import TestCase
from django.utils import timezone

from accounts.models import Student, Organization
from text_scheduler.models import LearningMaterial, StudentUnitProgress
from text_scheduler.services.daily_plan import (
    generate_or_get_today_plan,
    DEFAULT_DAILY_MINUTES_BUDGET,
    OVERDUE_REVIEW_STRICT_RATIO,
    OVERTIME_NEW_CAP,
)


class TestDailyPlanBackcasting(TestCase):

    def _make_student(self, username="stu"):
        org = Organization.objects.create(name=f"org_{username}")
        return Student.objects.create_user(
            email=None, password="pass", role="student", username=username,
            organization=org,
        )

    def _make_material(self, student, start_date, goal_date, total_units=30, required_reviews=3, estimated_minutes=5, buffer_weekdays=None):
        return LearningMaterial.objects.create(
            target_student=student,
            created_by=student,
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

    def _nth_weekday(self, d, weekday):
        add = (weekday - d.weekday()) % 7
        return d + dt.timedelta(days=add)

    def test_new_is_zero_on_buffer_day(self):
        stu = self._make_student("stu_buf")
        today = timezone.localdate()
        start = today
        goal = today + dt.timedelta(days=30)

        mat = self._make_material(stu, start, goal, total_units=20, buffer_weekdays=[5, 6])

        sat = self._nth_weekday(today, 5)
        plan = generate_or_get_today_plan(mat, date=sat)
        self.assertEqual(plan.suggested_new_count, 0)
        self.assertEqual(plan.estimated_total_minutes, 0)

    def test_new_stops_when_reviews_over_budget(self):
        stu = self._make_student("stu_over")
        today = timezone.localdate()
        start = today
        goal = today + dt.timedelta(days=10)
        est_m = 5
        mat = self._make_material(stu, start, goal, total_units=40, estimated_minutes=est_m)

        threshold_minutes = int(DEFAULT_DAILY_MINUTES_BUDGET * OVERDUE_REVIEW_STRICT_RATIO)
        need_reviews = (threshold_minutes // est_m) + 1
        due_dt = timezone.now() - dt.timedelta(days=1)
        for i in range(1, need_reviews + 1):
            StudentUnitProgress.objects.create(
                student=stu, material=mat, number=i,
                status="reviewing", repetition_count=2, interval_days=6,
                next_due_at=due_dt,
            )

        plan = generate_or_get_today_plan(mat, date=today)
        self.assertEqual(plan.suggested_new_count, 0, "レビュー渋滞日は新規が0になるはず")
        self.assertGreaterEqual(plan.estimated_total_minutes, threshold_minutes)

    def test_new_is_capped_in_overtime_mode(self):
        stu = self._make_student("stu_overdue")
        today = timezone.localdate()
        start = today - dt.timedelta(days=40)
        goal = today - dt.timedelta(days=1)
        mat = self._make_material(stu, start, goal, total_units=10)

        plan = generate_or_get_today_plan(mat, date=today)
        self.assertLessEqual(plan.suggested_new_count, max(0, int(OVERTIME_NEW_CAP)))

    def test_new_is_zero_after_all_initial_done(self):
        stu = self._make_student("stu_all")
        today = timezone.localdate()
        start = today
        goal = today + dt.timedelta(days=20)
        total_units = 12
        mat = self._make_material(stu, start, goal, total_units=total_units)

        past = timezone.now() - dt.timedelta(days=2)
        for i in range(1, total_units + 1):
            StudentUnitProgress.objects.create(
                student=stu, material=mat, number=i,
                status="learning", repetition_count=1, interval_days=1,
                next_due_at=past,
            )

        plan = generate_or_get_today_plan(mat, date=today)
        self.assertEqual(plan.suggested_new_count, 0)

    def test_backcasting_and_time_budget_hold(self):
        stu = self._make_student("stu_bc")
        today = timezone.localdate()
        start = today
        goal = today + dt.timedelta(days=25)
        est_m = 5
        total_units = 25
        mat = self._make_material(
            stu, start, goal, total_units=total_units,
            estimated_minutes=est_m, buffer_weekdays=[6]
        )

        plan = generate_or_get_today_plan(mat, date=today)
        self.assertGreaterEqual(plan.suggested_new_count, 0)
        self.assertLessEqual(plan.estimated_total_minutes, DEFAULT_DAILY_MINUTES_BUDGET)
