# tests/test_specific_linear_equation_generator.py
from django.test import SimpleTestCase
from unittest.mock import patch
import sympy as sy

# あなたの実装の import パスに合わせて変更してください
from math_trainer.math_process.junior_high1.specific_linear_equation_generator import SpecificLinearEquationGenerator


def I(n: int):
    """整数の (sympy値, latex文字列) を返す"""
    x = sy.Integer(n)
    return x, sy.latex(x)

def F(p: int, q: int):
    """有理数 p/q の (sympy値, latex文字列) を返す（表示は分数）"""
    x = sy.Rational(p, q)
    return x, sy.latex(x)

def D(tenths: int):
    """
    十分位小数 (tenths/10) を返す。
    計算は Rational、表示は Float の方針に合わせる。
    """
    x = sy.Rational(tenths, 10)
    return x, sy.latex(sy.Float(x))

def to_tenth(x: sy.Rational) -> sy.Rational:
    """Rational を最近似の 1/10 単位に四捨五入"""
    n10 = sy.Integer(sy.floor(x*10 + sy.Rational(1, 2)))
    return sy.Rational(n10, 10)

def fmt_for_choice_decimal(x: sy.Rational) -> str:
    """decimal-only のときの選択肢表示整形をテスト側にも再現"""
    return sy.latex(sy.Float(to_tenth(x)))

class StubGen(SpecificLinearEquationGenerator):
    """
    _make_random_number をキューで差し替えたテスト用のサブクラス。
    生成器が順に呼ぶ値を (sympy値, latex文字列) で与える。
    """
    def __init__(self, queue, **settings):
        super().__init__(**settings)
        self._queue = list(queue)

    def _make_random_number(self, number_type=None, max_num=5, min_num=-5):
        if not self._queue:
            raise AssertionError("Stub queue is empty")
        return self._queue.pop(0)


class SpecificLinearEquationGeneratorTests(SimpleTestCase):

    # ---------- ax = b（整数解） ----------
    def test_ax_equal_b_only_integer_basic(self):
        # answer=3, a=2 -> b=6
        q = [I(3), I(2)]
        gen = StubGen(
            q, numbers_to_use=["integer", "frac"],
            problem_types=["ax_equal_b_only_integer"],
        )
        ans, prob, choices = gen._make_ax_equal_b_only_integer()

        self.assertEqual(ans, r"\( x = 3 \)")
        self.assertEqual(prob, r"\( 2x = 6 \)")
        self.assertEqual(len(choices), 4)
        self.assertEqual(len(set(choices)), 4)
        self.assertIn(ans, choices)  # 正答が選択肢に含まれる

    # ---------- ax = b（分数/小数解含む, decimal-only） ----------
    def test_ax_equal_b_all_number_decimal_only(self):
        # answer=0.7 (=7/10), a=3 -> b=2.1
        q = [D(7), I(3)]
        gen = StubGen(
            q, numbers_to_use=["decimal"],  # decimal_only=True
            problem_types=["ax_equal_b_all_number"],
        )
        ans, prob, choices = gen._make_ax_equal_b_all_number()

        self.assertEqual(ans, r"\( x = 0.7 \)")
        self.assertEqual(prob, r"\( 3x = 2.1 \)")
        self.assertEqual(len(choices), 4)
        self.assertEqual(len(set(choices)), 4)
        self.assertIn(ans, choices)

    # ---------- ax + b = c（整数解） ----------
    def test_ax_plus_b_equal_c_only_integer_basic(self):
        # answer=3, a=2, c=10 -> b = 10 - 2*3 = 4
        q = [I(3), I(2), I(10)]
        gen = StubGen(
            q, numbers_to_use=["integer", "frac"],
            problem_types=["ax_plus_b_equal_c_only_integer"],
        )
        ans, prob, choices = gen._make_ax_plus_b_equal_c_only_integer()

        self.assertEqual(ans, r"\( x = 3 \)")
        self.assertEqual(prob, r"\( 2x+ 4= 10 \)")
        self.assertEqual(len(choices), 4)
        self.assertEqual(len(set(choices)), 4)
        self.assertIn(ans, choices)

    # ---------- ax + b = c（分数解含む, 非decimal-only） ----------
    def test_ax_plus_b_equal_c_all_number_fraction(self):
        # answer=3/2, a=2, c=5 -> b = 5 - 2*(3/2) = 2
        q = [F(3, 2), I(2), I(5)]
        gen = StubGen(
            q, numbers_to_use=["integer", "frac"],  # decimal_only=False
            problem_types=["ax_plus_b_equal_c_all_number"],
        )
        ans, prob, choices = gen._make_ax_plus_b_equal_c_all_number()

        self.assertEqual(ans, r"\( x = \frac{3}{2} \)")
        self.assertEqual(prob, r"\( 2x+ 2= 5 \)")
        self.assertEqual(len(choices), 4)
        self.assertEqual(len(set(choices)), 4)
        self.assertIn(ans, choices)

    # ---------- ax + b = cx + d（整数解, random分岐: bを先に固定） ----------
    @patch("math_trainer.math_process.junior_high1.specific_linear_equation_generator.random", return_value=0.9)
    def test_ax_plus_b_equal_cx_plus_d_only_integer_branch_b_first(self, _mock_random):
        # answer=3, a=2, c=1, b=4  -> d = a*ans + b - c*ans = 2*3 + 4 - 3 = 7
        q = [I(3), I(2), I(1), I(4)]
        gen = StubGen(
            q, numbers_to_use=["integer", "frac"],
            problem_types=["ax_plus_b_equal_cx_plus_d_only_integer"],
        )
        ans, prob, choices = gen._make_ax_plus_b_equal_cx_plus_d_only_integer()

        self.assertEqual(ans, r"\( x = 3 \)")
        self.assertEqual(prob, r"\( 2x+ 4= x+ 7 \)")
        self.assertEqual(len(choices), 4)
        self.assertEqual(len(set(choices)), 4)
        self.assertIn(ans, choices)

    # ---------- ax + b = cx + d（整数解, random分岐: dを先に固定） ----------
    @patch("math_trainer.math_process.junior_high1.specific_linear_equation_generator.random", return_value=0.1)
    def test_ax_plus_b_equal_cx_plus_d_only_integer_branch_d_first(self, _mock_random):
        # answer=2, a=3, c=-1, d=5 -> b = -a*ans + c*ans + d = -6 -2 + 5 = -3
        q = [I(2), I(3), I(-1), I(5)]
        gen = StubGen(
            q, numbers_to_use=["integer", "frac"],
            problem_types=["ax_plus_b_equal_cx_plus_d_only_integer"],
        )
        ans, prob, choices = gen._make_ax_plus_b_equal_cx_plus_d_only_integer()

        self.assertEqual(ans, r"\( x = 2 \)")
        self.assertEqual(prob, r"\( 3x-3= -x+ 5 \)")
        self.assertEqual(len(choices), 4)
        self.assertEqual(len(set(choices)), 4)
        self.assertIn(ans, choices)

    # ---------- ax + b = cx + d（分数/小数解含む, decimal-only, 分岐: d先） ----------
    @patch("math_trainer.math_process.junior_high1.specific_linear_equation_generator.random", return_value=0.1)
    def test_ax_plus_b_equal_cx_plus_d_all_number_decimal_only(self, _mock_random):
        # answer=0.7, a=2, c=-1, d=1.5 -> b = -a*ans + c*ans + d = -1.4 -0.7 + 1.5 = -0.6
        q = [D(7), I(2), I(-1), D(15)]
        gen = StubGen(
            q, numbers_to_use=["decimal"],  # decimal-only
            problem_types=["ax_plus_b_equal_cx_plus_d_all_number"],
        )
        ans, prob, choices = gen._make_ax_plus_b_equal_cx_plus_d_all_number()

        # 正答（選択肢側の表示は fmt_for_choice を使う実装）
        self.assertEqual(ans, r"\( x = 0.7 \)")
        self.assertEqual(prob, r"\( 2x-0.6= -x+ 1.5 \)")
        self.assertEqual(len(choices), 4)
        self.assertEqual(len(set(choices)), 4)
        # decimal-only の all_number 版は choices の正答も十分位表示に揃える実装
        correct_choice = r"\( x = " + fmt_for_choice_decimal(sy.Rational(7, 10)) + r" \)"
        self.assertIn(correct_choice, choices)

    # ---------- _build_one() の基本形検査 ----------
    def test_build_one_shape(self):
        # 単一タイプに絞って generate()
        q = [I(3), I(2)]  # ax=b only integer
        gen = StubGen(
            q, numbers_to_use=["integer", "frac"],
            problem_types=["ax_equal_b_only_integer"],
        )
        payload = gen.generate()
        self.assertIn("problem_text", payload)
        self.assertIn("answer_text", payload)
        self.assertIn("choices", payload)
        self.assertIsInstance(payload["choices"], list)
        self.assertEqual(len(payload["choices"]), 4)
        self.assertEqual(len(set(payload["choices"])), 4)
