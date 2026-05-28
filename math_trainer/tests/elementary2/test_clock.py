# tests.py
from django.test import SimpleTestCase
from unittest.mock import patch

# ↓プロジェクトの実際の配置に合わせて修正してください
from math_trainer.math_process.elementary2.clock_generator import (
    TimeInformation, ClockProblemGenerator
)

class TimeInformationTests(SimpleTestCase):
    def test_to_datetime_24h(self):
        t = TimeInformation(23, 45)
        self.assertEqual(t.to_datetime().hour, 23)
        self.assertEqual(t.to_datetime().minute, 45)

    def test_to_datetime_am_pm(self):
        self.assertEqual(TimeInformation(12, 0, "am").to_datetime().hour, 0)   # 午前12時=0時
        self.assertEqual(TimeInformation(12, 0, "pm").to_datetime().hour, 12)  # 午後12時=12時
        self.assertEqual(TimeInformation(1, 0, "pm").to_datetime().hour, 13)

    def test_add_and_subtract_minutes_keep_format(self):
        self.assertEqual(str(TimeInformation(23, 55).add_or_subtract_minutes(10)), "0時5分")  # 24hのまま
        self.assertEqual(str(TimeInformation(11, 55, "am").add_or_subtract_minutes(10)), "午後12時5分")  # AM/PM維持

    def test_difference_in_minutes(self):
        a = TimeInformation(10, 30)
        b = TimeInformation(9, 45)
        self.assertEqual(a.difference_in_minutes(b), 45)

    def test_str_format(self):
        self.assertEqual(str(TimeInformation(3, 0)), "3時")
        self.assertEqual(str(TimeInformation(3, 5)), "3時5分")
        self.assertEqual(str(TimeInformation(12, 0, "am")), "午前12時")
        self.assertEqual(str(TimeInformation(12, 0, "pm")), "午後12時")
        self.assertEqual(str(TimeInformation(1, 5, "pm")), "午後1時5分")


class CalculateBoundsTests(SimpleTestCase):
    def setUp(self):
        self.gen = ClockProblemGenerator(
            problem_types=["time_delta_with_24_hours_without_picture"],
            widths_of_time=["less_than_one_hour"],
        )

    def test_before_bound_uses_00_01_as_lower_limit(self):
        # 1:10 から before の最大は 69分（= 1:10 → 0:01）
        word, max_minutes = self.gen.calculate_bounds(TimeInformation(1, 10), "before", use_24h_limit=True)
        self.assertEqual(word, "前")
        self.assertEqual(max_minutes, 69)

    def test_after_bound_24h(self):
        # 23:30 の after の最大は 29分（23:59超えない）
        word, max_minutes = self.gen.calculate_bounds(TimeInformation(23, 30), "after", use_24h_limit=True)
        self.assertEqual(word, "後")
        self.assertEqual(max_minutes, 29)

    def test_after_bound_12h(self):
        # 11:10 の after の最大は 49分（11:59超えない）
        word, max_minutes = self.gen.calculate_bounds(TimeInformation(11, 10), "after", use_24h_limit=False)
        self.assertEqual(word, "後")
        self.assertEqual(max_minutes, 49)


class PickValidDeltaTests(SimpleTestCase):
    def setUp(self):
        self.gen = ClockProblemGenerator(
            problem_types=["time_delta_with_24_hours_without_picture"],
            widths_of_time=["less_than_one_hour"],
        )

    @patch("math_trainer.math_process.elementary2.clock_generator.choice", return_value="after")
    @patch("math_trainer.math_process.elementary2.clock_generator.randint", return_value=30)
    def test_less_than_one_hour_range(self, mocked_randint, mocked_choice):
        # 10:00, less_than_one_hour なら 1..59 の範囲で返る
        before_or_after, word, delta, maxm = self.gen.pick_valid_delta(
            TimeInformation(10, 0), "less_than_one_hour", use_24h_limit=True
        )
        self.assertEqual(before_or_after, "after")
        self.assertEqual(word, "後")
        self.assertTrue(1 <= delta <= 59)
        self.assertTrue(maxm >= delta)

    @patch("math_trainer.math_process.elementary2.clock_generator.choice", return_value="after")
    @patch("math_trainer.math_process.elementary2.clock_generator.randint", return_value=120)
    def test_gte_one_hour_range(self, mocked_randint, mocked_choice):
        before_or_after, word, delta, maxm = self.gen.pick_valid_delta(
            TimeInformation(10, 0), "greater_than_or_equal_to_one_hour", use_24h_limit=True
        )
        self.assertEqual(before_or_after, "after")
        self.assertEqual(word, "後")
        self.assertGreaterEqual(delta, 60)
        self.assertTrue(maxm >= delta)


class GenerateDummyMinutesTests(SimpleTestCase):
    def setUp(self):
        self.gen = ClockProblemGenerator(
            problem_types=["time_delta_with_24_hours_without_picture"],
            widths_of_time=["less_than_one_hour"],
        )

    def test_generate_dummies_sign_and_size_before(self):
        # max_minutes=59, 正解=30分, before → ダミーは負数3件
        dums = self.gen.generate_minutes_for_dummy(
            "less_than_one_hour", 59, 30, "before"
        )
        self.assertEqual(len(dums), 3)
        self.assertTrue(all(m < 0 for m in dums))
        self.assertTrue(all(-59 <= m <= -1 for m in dums))
        self.assertTrue(30 not in map(abs, dums))  # 正解と重複しない

    def test_generate_dummies_error_when_impossible(self):
        # 範囲が実質1分しかなく、しかも正解がその1分 → 生成不能で RuntimeError
        with self.assertRaises(RuntimeError):
            self.gen.generate_minutes_for_dummy(
                "less_than_one_hour", max_minutes=1, delta_minutes_for_answer=1, before_or_after="after"
            )


class MakeProblemUnitTests(SimpleTestCase):
    def setUp(self):
        self.gen = ClockProblemGenerator(
            problem_types=["time_delta_without_am_pm_with_picture"],
            widths_of_time=["greater_than_or_equal_to_one_hour"],
        )

    @patch.object(ClockProblemGenerator, "pick_valid_delta", return_value=("before", "前", 75, 200))
    def test_make_time_delta_without_am_pm_problem(self, _):
        # 基準: 5:20, 答え: 1時間15分前 → 4:05
        with patch("math_trainer.math_process.elementary2.clock_generator.randint", side_effect=[5, 20]):
            answer, problem, base_time, choices = self.gen._make_time_delta_without_am_pm_problem(
                "greater_than_or_equal_to_one_hour"
            )
        self.assertEqual(str(base_time), "5時20分")
        self.assertIn("1時間15分前は何時何分ですか", problem)
        self.assertEqual(answer, "4時5分")
        self.assertEqual(len(choices), 4)
        self.assertIn(answer, choices)

    def test_make_read_time_problem_shape(self):
        # 形（構造）と最低限の制約を検証（乱数固定は不要）
        answer, problem, t, choices = self.gen._make_read_time_problem()
        self.assertEqual(problem, "時計は何時何分ですか?")
        self.assertEqual(len(choices), 4)
        self.assertIn(answer, choices)
        # 1..12 時 / 1..59 分（現仕様）
        self.assertTrue(1 <= t.hour <= 12)
        self.assertTrue(1 <= t.minute <= 59)


class GenerateAPITests(SimpleTestCase):
    def test_generate_returns_expected_shape_single(self):
        gen = ClockProblemGenerator(
            problem_types=["time_delta_with_24_hours_without_picture"],
            widths_of_time=["less_than_one_hour"],
        )
        data = gen.generate()
        self.assertIn("problem_text", data)
        self.assertIn("answer_text", data)
        self.assertIn("choices", data)
        self.assertIn("metadata", data)
        self.assertIn("draw", data["metadata"])
        self.assertIn("canvas_required", data["metadata"])
        ti = data["metadata"]["draw"]["time_information"]
        self.assertTrue(isinstance(ti, list))
        self.assertTrue(all("hour" in x and "minute" in x for x in ti))

    def test_generate_with_two_clocks_has_double_type(self):
        gen = ClockProblemGenerator(
            problem_types=["time_delta_with_two_clock_pictures"],
            widths_of_time=["less_than_one_hour"],
        )
        data = gen.generate()
        self.assertEqual(data["metadata"]["draw"]["type"], "double")
        self.assertEqual(len(data["metadata"]["draw"]["time_information"]), 2)
