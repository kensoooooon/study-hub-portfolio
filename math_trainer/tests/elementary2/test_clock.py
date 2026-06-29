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
    """pick_valid_delta() が返す値の妥当性を検証する。

    リファクタ後は choice/randint ではなく _build_delta_pool() ベースの方向列挙に
    変わったため、モックを使わず実際の戻り値の範囲を確認する。
    """

    def setUp(self):
        self.gen = ClockProblemGenerator(
            problem_types=["time_delta_with_24_hours_without_picture"],
            widths_of_time=["less_than_one_hour"],
        )

    def test_less_than_one_hour_returns_delta_in_valid_range(self):
        # 10:00 は before/after 両方とも十分な余裕があるため必ず成功する。
        # less_than_one_hour なので delta は 1..59 の範囲に収まるはず。
        before_or_after, word, delta, maxm = self.gen.pick_valid_delta(
            TimeInformation(10, 0), "less_than_one_hour", use_24h_limit=True
        )
        self.assertIn(before_or_after, ["before", "after"])
        self.assertTrue(1 <= delta <= 59)
        self.assertGreaterEqual(maxm, delta)

    def test_gte_one_hour_returns_delta_at_least_60(self):
        # 10:00 は before/after 両方とも十分な余裕があるため必ず成功する。
        # greater_than_or_equal_to_one_hour なので delta >= 60 のはず。
        before_or_after, word, delta, maxm = self.gen.pick_valid_delta(
            TimeInformation(10, 0), "greater_than_or_equal_to_one_hour", use_24h_limit=True
        )
        self.assertIn(before_or_after, ["before", "after"])
        self.assertGreaterEqual(delta, 60)
        self.assertGreaterEqual(maxm, delta)


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


class BuildDeltaPoolTests(SimpleTestCase):
    """_build_delta_pool() の境界値テスト。

    width_of_time と max_minutes の組み合わせに対して正しい候補リストを返すことを確認する。
    pick_valid_delta() と generate_minutes_for_dummy() が同じ pool を共有する前提となるため、
    この helper の正確さが全体の一貫性を保証する。
    """

    def setUp(self):
        self.gen = ClockProblemGenerator(
            problem_types=["read_time"],
            widths_of_time=["less_than_one_hour"],
        )

    def test_less_than_one_hour_returns_1_to_max(self):
        # max_minutes=30 → [1, 2, ..., 30]
        self.assertEqual(self.gen._build_delta_pool("less_than_one_hour", 30), list(range(1, 31)))

    def test_less_than_one_hour_caps_at_59(self):
        # max_minutes が 59 を超える場合は 59 でキャップされる
        self.assertEqual(self.gen._build_delta_pool("less_than_one_hour", 120), list(range(1, 60)))

    def test_less_than_one_hour_zero_max_returns_empty(self):
        # max_minutes=0 は 1 分も動けない → 空リスト
        self.assertEqual(self.gen._build_delta_pool("less_than_one_hour", 0), [])

    def test_less_than_one_hour_negative_max_returns_empty(self):
        # max_minutes が負の場合も空リストを返す
        self.assertEqual(self.gen._build_delta_pool("less_than_one_hour", -1), [])

    def test_gte_one_hour_returns_60_to_max(self):
        # max_minutes=90 → [60, 61, ..., 90]
        self.assertEqual(self.gen._build_delta_pool("greater_than_or_equal_to_one_hour", 90), list(range(60, 91)))

    def test_gte_one_hour_exactly_60_returns_single_element(self):
        # max_minutes=60 → [60] のみ（pool サイズ 1 なので pick_valid_delta では使われない）
        self.assertEqual(self.gen._build_delta_pool("greater_than_or_equal_to_one_hour", 60), [60])

    def test_gte_one_hour_below_60_returns_empty(self):
        # max_minutes=59 は 60 分以上を取れない → 空リスト
        self.assertEqual(self.gen._build_delta_pool("greater_than_or_equal_to_one_hour", 59), [])

    def test_invalid_width_raises_value_error(self):
        # 想定外の width_of_time は ValueError を送出する
        with self.assertRaises(ValueError):
            self.gen._build_delta_pool("invalid_width", 30)


class PickValidDeltaDirectionFallbackTests(SimpleTestCase):
    """pick_valid_delta() の方向フォールバック動作を検証する。

    before 側の候補が不足していても after 側が有効なら成功することと、
    両方向とも候補が不足する場合に RuntimeError が送出されることを確認する。
    """

    def setUp(self):
        self.gen = ClockProblemGenerator(
            problem_types=["time_delta_with_24_hours_without_picture"],
            widths_of_time=["less_than_one_hour"],
        )

    def test_narrow_before_wide_after_selects_after(self):
        # 0:03 (24時間制, use_24h_limit=True):
        #   before: 0:03 → 0:01 = 2分 → pool=[1,2] (2件 < 4) → 無効
        #   after:  0:03 → 23:59 = 23時間56分 = 1436分 → pool=[1..59] (59件) → 有効
        # よって必ず after が選ばれる
        before_or_after, word, delta, maxm = self.gen.pick_valid_delta(
            TimeInformation(0, 3), "less_than_one_hour", use_24h_limit=True
        )
        self.assertEqual(before_or_after, "after")
        self.assertEqual(word, "後")
        self.assertTrue(1 <= delta <= 59)

    def test_wide_before_narrow_after_selects_before(self):
        """
        後ろに広げられない条件であれば、前が選ばれる
        """
        before_or_after, word, delta, maxm = self.gen.pick_valid_delta(
            TimeInformation(23, 58), "less_than_one_hour", use_24h_limit=True
        )
        self.assertEqual(before_or_after, "before")
        self.assertEqual(word, "前")
        self.assertTrue(1 <= delta <= 59)

    def test_raises_runtime_error_when_no_valid_options(self):
        # _build_delta_pool を常に空リストを返すようにモックすると、
        # 両方向とも pool < 4 になり RuntimeError が送出される
        with patch.object(self.gen, "_build_delta_pool", return_value=[]):
            with self.assertRaises(RuntimeError) as ctx:
                self.gen.pick_valid_delta(
                    TimeInformation(10, 0), "less_than_one_hour", use_24h_limit=True
                )
        self.assertIn("Could not pick a valid delta_minutes", str(ctx.exception))


class PickValidDeltaAndDummyConsistencyTests(SimpleTestCase):
    """pick_valid_delta() → generate_minutes_for_dummy() の一貫性を検証する。

    pick_valid_delta() が返した delta を使って generate_minutes_for_dummy() を呼ぶと、
    必ずダミー3件が生成されること（Issue #21 の再現ケースを含む）を確認する。
    """

    def setUp(self):
        self.gen = ClockProblemGenerator(
            problem_types=["time_delta_without_am_pm_with_picture"],
            widths_of_time=["less_than_one_hour"],
        )

    def _call_pair(self, time, width, use_24h):
        """pick_valid_delta → generate_minutes_for_dummy を連続して呼び出す"""
        before_or_after, word, delta, max_m = self.gen.pick_valid_delta(
            time, width, use_24h_limit=use_24h
        )
        dummies = self.gen.generate_minutes_for_dummy(width, max_m, delta, before_or_after)
        return dummies

    def test_known_narrow_before_case_does_not_raise(self):
        # Issue #21 の再現ケース相当:
        # 0:03 (24時間制) は before 側が pool 2件のみで不足するが、
        # pick_valid_delta() が after を選ぶため generate_minutes_for_dummy() は3件返す
        dummies = self._call_pair(TimeInformation(0, 3), "less_than_one_hour", use_24h=True)
        self.assertEqual(len(dummies), 3)
        self.assertTrue(all(m > 0 for m in dummies))  # after なので正数

    def test_gte_one_hour_narrow_before_case_does_not_raise(self):
        # Issue #21 の再現ケース相当 (>=1h):
        # 23:58 (use_24h_limit=True):
        #   after: max=1分 → pool=[] → 無効
        #   before: max=23*60+57=1437分 → pool=[60..1437] → 有効
        dummies = self._call_pair(
            TimeInformation(23, 58), "greater_than_or_equal_to_one_hour", use_24h=True
        )
        self.assertEqual(len(dummies), 3)

    def test_generate_dummy_does_not_raise_could_not_prepare_error(self):
        # 決定的条件: 10:30 は before/after 双方とも余裕があり必ず成功する。
        # ダミー生成 RuntimeError が出ないことを明示的に確認する。
        try:
            dummies = self._call_pair(TimeInformation(10, 30), "less_than_one_hour", use_24h=True)
        except RuntimeError as e:
            self.fail(f"generate_minutes_for_dummy が RuntimeError を送出した: {e}")
        self.assertEqual(len(dummies), 3)


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
