from random import choice, randint, random, shuffle

import sympy as sy

from math_trainer.math_process.base_generator import BaseProblemGenerator

from dataclasses import dataclass

class InvalidSettingsError(ValueError):
    pass

@dataclass
class EqParts:
    """
    二元一次方程式をax+by=cに整理したときの各係数、およびlatex化された式をまとめて格納
    
    Attributes:
        A (sy.Rational): xの係数
        B (sy.Rational): yの係数
        C (sy.Rational): 定数
        latex (str): その式を表すlatex(開始記号,終了記号はなし)
    """
    A: sy.Rational
    B: sy.Rational
    C: sy.Rational
    latex: str


class SimultaneousEquationsGenerator(BaseProblemGenerator):
    """連立方程式の解を求める問題を出力する
    
    Args:
        BaseProblemGenerator: 全体に共通する問題の設定
    
    Attributes:
        equation_types (list[str]): 式の形と解の指定
        used_coefficients (list[str]): 優先的に利用する係数
        choices (list[str]): 問題の選択肢。正解が1つで偽答が3つ
        latex_answer (str): latex形式で記述された解答
        latex_problem (str): latex形式で記述された問題
    
    Note:
        LaTex表示に必要な整形は全てこちらでやる想定
    """
    def __init__(self, **settings: dict):
        """初期化
        
        Args:
            settings (dict): 問題の設定が格納されている
        """
        super().__init__(**settings)
        self.equation_types = settings['equation_types']
        self.used_coefficients = settings['used_coefficients']
        self.answer_types = settings["answer_types"]
        
        # ホワイトリスト
        ok_eq = {"ax+by=c", "ax+by=c+dx+ey", "ax+by=c+d(ex+fy)"}
        ok_coef = {"integer", "frac", "decimal"}
        ok_ans = {"only_integer", "including_fraction_and_decimal"}

        eq_set = set(self.equation_types)
        coef_set = set(self.used_coefficients)
        ans_set = set(self.answer_types)

        if not eq_set or not eq_set <= ok_eq:
            raise InvalidSettingsError(f"Invalid equation_types: {self.equation_types}")
        if not coef_set or not coef_set <= ok_coef:
            raise InvalidSettingsError(f"Invalid used_coefficients: {self.used_coefficients}")
        if not ans_set or not ans_set <= ok_ans:
            raise InvalidSettingsError(f"Invalid answer_types: {self.answer_types}")
    
    def _build_one(self):
        """選択された1次方程式の形に応じて、1問単位の問題と解答を出力する
        
        Returns:
            latex_answer (str): latex形式で記述された解答
            latex_problem (str): latex形式で記述されたされた問題
        """
        # 解を先に確定させる
        (answer_x, answer_x_latex), (answer_y, answer_y_latex) = self._make_two_answers()        
        # 問題文作成
        problem_text, has_unique_answer = self._make_problem_text(answer_x, answer_y)
        if has_unique_answer:
            answer_text = f"\( x = {answer_x_latex}, \quad y = {answer_y_latex} \)"
        else:
            answer_text = "解は無数に存在する"
        # 選択肢作成
        choices = self._make_choices(answer_x, answer_y, answer_text)
        
        return {
            "problem_text": problem_text,
            "answer_text": answer_text,
            "choices": choices,
            "metadata": {},
        }
    
    def generate(self):
        return self._build_one()

    def _make_two_answers(self):
        """2つの解を選択された解のタイプに基づいて出力
        
        Returns:
            answer1 (sy.Integer or sy.Rational): 計算に用いる1つ目の解
            answer1_latex (str): 表示に用いる1つ目の解
            answer2 (sy.Integer or sy.Rational): 計算に用いる2つ目の解
            answer2_latex (str): 表示に用いる2つ目の解
        """
        answers = []
        # 都度抽選
        for _ in range(2):
            answer_type = choice(self.answer_types)
            if answer_type == "only_integer":
                answer, answer_latex = self._random_num_maker(number_type="integer")
            elif answer_type == "including_fraction_and_decimal":
                # 係数も小数オンリーのときのみ小数解
                if set(self.used_coefficients) == {"decimal"}:
                    number_type = "decimal"
                else:
                    number_type = choice(["integer", "frac"])
                answer, answer_latex = self._random_num_maker(number_type=number_type)
            answers.append((answer, answer_latex))
        (answer1, answer1_latex), (answer2, answer2_latex) = answers
        return (answer1, answer1_latex), (answer2, answer2_latex)
    
    def _make_choices(self, answer_x, answer_y, answer_text):
        """
        与えられた条件から3つのダミーを含む選択肢を返す
        
        Args:
            answer_x, answer_y (sy.Rational): 連立方程式の解
            answer_text (str): 答えの文章 
        """
        choices = [answer_text]
        if answer_text == "解は無数に存在する":
            choices.append("解は存在しない")
            choices.append("ただ一組の解が存在する")
            choices.append("いずれも正しくない")
        else:
            dummies = set()
            
            def safe_add(new_x, new_y):
                if ((new_x, new_y) != (answer_x, answer_y)):
                    dummies.add((new_x, new_y))

            # 近傍
            for dp in range(1, 5):
                safe_add(answer_x - dp, answer_y - dp)
                safe_add(answer_x - dp, answer_y + dp)
                safe_add(answer_x + dp, answer_y - dp)
                safe_add(answer_x + dp, answer_y + dp)
            
            # フォールバック
            if len(dummies) < 3:
                # 範囲拡張
                for dp in range(5, 10):
                    safe_add(answer_x - dp, answer_y - dp)
                    safe_add(answer_x - dp, answer_y + dp)
                    safe_add(answer_x + dp, answer_y - dp)
                    safe_add(answer_x + dp, answer_y + dp)
            
            dummies = list(dummies)
            shuffle(dummies)
            for dummy_x, dummy_y in dummies[:3]:
                dummy_text = f"\( x = {sy.latex(dummy_x)}, \quad y = {sy.latex(dummy_y)} \)"
                choices.append(dummy_text)
        shuffle(choices)
        return choices

    def _build_equation(self, answer_x, answer_y) -> EqParts:
        """
        問題の設定に応じた式を1つ返す
        
        Args:
            answer_x, answer_y (sy.Rational): 連立方程式の解
        
        Returns:
            EqParts (dataclass): ax+by=cのa,b,cと、problem_textが格納
        """
        equation_type = choice(self.equation_types)
        if equation_type == "ax+by=c":
            return self._make_ax_plus_by_equal_c(answer_x, answer_y)
        elif equation_type == "ax+by=c+dx+ey":
            return self._make_ax_plus_by_equal_c_plus_dx_plus_ey(answer_x, answer_y)
        elif equation_type == "ax+by=c+d(ex+fy)":
            return self._make_ax_plus_by_equal_c_plus_d_ex_plus_fy(answer_x, answer_y)
        else:
            raise ValueError(f"Unexpected equation_type: {equation_type}")

    def _make_problem_text(self, answer_x, answer_y):
        """
        与えられた解と問題の設定から問題文を作成する
        
        Args:
            answer_x, answer_y (sy.Rational):x,yの解
        
        Returns:
            problem_text (str): 連立方程式として表示されるLaTeXの文
            has_unique_answer (bool): True: 一意な解を持つ, False: 無数に解を持つ
        """
        max_retry = 20
        for _ in range(max_retry):
            eq_parts1 = self._build_equation(answer_x, answer_y)
            eq_parts2 = self._build_equation(answer_x, answer_y)
            a1, b1 = eq_parts1.A, eq_parts1.B
            a2, b2 = eq_parts2.A, eq_parts2.B
            # 判別式が0でない=一意な解を持つか
            if sy.Matrix([[a1, b1], [a2, b2]]).det() != 0:
                equation1, equation2 = eq_parts1.latex, eq_parts2.latex
                has_unique_answer = True
                break
        # フェイルセーフ
        else:
            equation1, equation2 = eq_parts1.latex, eq_parts2.latex
            has_unique_answer = False

        # 実際の問題文作成
        problem_text = "\\( "
        problem_text += ""
        problem_text += "\\begin{cases}"
        problem_text += equation1
        problem_text += "\\\\"
        problem_text += equation2
        problem_text += "\\end{cases}"
        
        problem_text += " \\)"
        return problem_text, has_unique_answer

    def _to_decimal_latex(self, q: sy.Rational, places: int = 6) -> str:
        """有限小数なら10進表記、そうでなければ分数表記で latex を返す"""
        if self._is_finite_decimal(q) and (not q.is_Integer):
            # places桁の10進表示（丸めはSympy任せ）。教材なら 3〜6 桁で十分
            return sy.latex(sy.N(q, places))
        return sy.latex(q)


    def _make_ax_plus_by_equal_c(self, answer_x, answer_y):
        """指定された解を持つax+by=c型の問題を作成
        Args:
            answer_x, answer_y (sy.Rational): 連立方程式の解となるx,y
        
        Return:
            (EqParts): 連立方程式の情報を持つデータクラス
        """        
        a, a_latex = self._random_num_maker()
        b, b_latex = self._random_num_maker() 
        c = a * answer_x + b * answer_y
        c_latex = self._to_decimal_latex(c)
            
        latex_equation = ""
        if a == 1:
            latex_equation += "x"
        elif a == -1:
            latex_equation += "- x"
        else:
            latex_equation += f"{a_latex}x"

        if b == 1:
            latex_equation += " + y"
        elif b == -1:
            latex_equation += " - y"
        elif b > 0:
            latex_equation += f"+ {b_latex}y"
        else:
            latex_equation += f"{b_latex}y"
        
        latex_equation += f" = {c_latex}"
        
        x_coeff = a
        y_coeff = b
        const = c
        return EqParts(x_coeff, y_coeff, const, latex_equation)
    
    def _make_ax_plus_by_equal_c_plus_dx_plus_ey(self, answer_x, answer_y):
        """ax+by=c+dx+ey型の問題を出力する

        Args:
            answer_x (sy.Integer or sy.Rational): 解その1
            answer_y (sy.Integer or sy.Rational): 解その2
        
        Return:
            (EqParts): 連立方程式の情報を持つデータクラス
        """        
        a, a_latex = self._random_num_maker(min_num=-4, max_num=4)
        b, b_latex = self._random_num_maker(min_num=-4, max_num=4)
        d, d_latex = self._random_num_maker(min_num=-3, max_num=3)
        e, e_latex = self._random_num_maker(min_num=-3, max_num=3)
        c = (a - d) * answer_x + (b - e) * answer_y
        c_latex = self._to_decimal_latex(c)
    
        latex_equation = ""
        if a == 1:
            latex_equation += "x"
        elif a == -1:
            latex_equation += "- x"
        else:
            latex_equation += f"{a_latex}x"

        if b == 1:
            latex_equation += " + y"
        elif b == -1:
            latex_equation += " - y"
        elif b > 0:
            latex_equation += f" + {b_latex}y"
        else:
            latex_equation += f" {b_latex}y"
        
        if c!= 0:
            latex_equation += f" = {c_latex}"
        else:
            latex_equation += "="
        
        if d == 1:
            if c != 0:
                latex_equation += " + x"
            else:
                latex_equation += "x"
        elif d == -1:
            latex_equation += " - x"
        elif d > 0:
            latex_equation += f" + {d_latex}x"
        else:
            latex_equation += f" {d_latex}x"

        if e == 1:
            latex_equation += " + y"
        elif e == -1:
            latex_equation += " - y"
        elif e > 0:
            latex_equation += f" + {e_latex}y"
        else:
            latex_equation += f" {e_latex}y"
        
        x_coeff = a - d
        y_coeff = b - e
        const = c
        return EqParts(x_coeff, y_coeff, const, latex_equation)

    def _make_ax_plus_by_equal_c_plus_d_ex_plus_fy(self, answer_x, answer_y):
        """ax+by=c+d(ex+fy)型の方程式を出力

        Args:
            answer_x (sy.Integer or sy.Rational): 解その1
            answer_y (sy.Integer or sy.Rational): 解その2
        
        Return:
            (EqParts): 連立方程式の情報を持つデータクラス
        """
        a, a_latex = self._random_num_maker(min_num=-4, max_num=4)
        b, b_latex = self._random_num_maker(min_num=-4, max_num=4)
        d, d_latex = self._random_num_maker(min_num=-2, max_num=2)
        e, e_latex = self._random_num_maker(min_num=-2, max_num=2)
        f, f_latex = self._random_num_maker(min_num=-2, max_num=2)
        c = (a - d * e) * answer_x + (b - d * f) * answer_y
        c_latex = self._to_decimal_latex(c)
        
        latex_equation = ""
        if a == 1:
            latex_equation += "x"
        elif a == -1:
            latex_equation += "- x"
        else:
            latex_equation += f"{a_latex}x"

        if b == 1:
            latex_equation += " + y"
        elif b == -1:
            latex_equation += " - y"
        elif b > 0:
            latex_equation += f" + {b_latex}y"
        else:
            latex_equation += f" {b_latex}y"
        
        if c != 0:
            latex_equation += f" = {c_latex}"
        else:
            latex_equation += "="
        
        if d == 1:
            latex_equation += f"+ \\left("
        elif d == -1:
            latex_equation += f"- \\left("
        elif d > 0:
            latex_equation += f"+ {d_latex}\\left("
        else:
            latex_equation += f"{d_latex}\\left("
        
        if e == 1:
            latex_equation += " x"
        elif e == -1:
            latex_equation += " - x"
        elif e > 0:
            latex_equation += f" {e_latex}x"
        else:
            latex_equation += f" {e_latex}x"

        if f == 1:
            latex_equation += " + y \\right)"
        elif f == -1:
            latex_equation += " - y \\right)"
        elif f > 0:
            latex_equation += f" + {f_latex}y \\right)"
        else:
            latex_equation += f" {f_latex}y \\right)"
        
        x_coeff = a - d * e
        y_coeff = b - d * f
        const = c
        return EqParts(x_coeff, y_coeff, const, latex_equation)
        
    def _random_num_maker(self, number_type=None, max_num=6, min_num=-6):
        """問題設定と最大最小から任意の数を値とlatex形式でランダムに出力

        Args:
            number_type (str, optional): integer, frac, decimalのいずれかの指定
            max_num (int, optional): 最大値
            min_num (int, optional): 最小値

        Returns:
            num (sy.Integer or sy.Rational): 計算に用いる数
            num_latex (str): 表記に用いる数
        
        Caution:
            小数についてはnumがsy.Rational型で、num_latexは小数を変換した文字列である差異に注意
        """
        if number_type is None:
            number_type = choice(self.used_coefficients)
        if number_type == "integer":
            num, num_latex = self._make_random_integer(max_num=max_num, min_num=min_num)
        elif number_type == "frac":
            num, num_latex = self._make_random_frac(max_num=max_num, min_num=min_num)
        elif number_type == "decimal":
            num, num_latex = self._make_random_decimal(max_num=max_num * 2, min_num=min_num * 2)
        return num, num_latex
    
    def _make_random_frac(self, max_num=6, min_num=-6):
        """ランダムな分数を返す

        Args:
            max_num (int, optional): 分母と分子の最大値
            min_num (int, optional): 分母と分子の最小値

        Returns:
            frac (sy.Rational): 分数
            frac_latex (str): latex形式で記述された分数
        """
        checker = random()
        if checker > 0.5:
            numerator = randint(2, max_num)
            denominator = randint(2, max_num)
        else:
            numerator = randint(min_num, -2)
            denominator = randint(2, max_num)
        
        frac = sy.Rational(numerator, denominator)
    
        frac_latex = sy.latex(frac)
        return frac, frac_latex
        
    def _make_random_decimal(self, max_num=30, min_num=-30):
        """ランダムで0.5刻みの小数を返す

        Args:
            max_num (int, optional): 小数作成用分数の分子の最大値
            min_num (int, optional): 小数作成用分数の分子の最小値
        Returns:
            frac_as_decimal (sy.Rational): 計算に用いる分数
            decimal_latex (str): 表記に用いる小数
        Note:
            計算自体は分数で行うため、表記に用いているものと型が違うことに注意
        """
        checker = random()
        if checker > 0.5:
            numerator = randint(1, max_num)
        else:
            numerator = randint(min_num, -1)
        
        if numerator % 10 == 0:
            numerator += randint(1, 5)
        frac_as_decimal = sy.Rational(numerator, 10)
        decimal_latex = self._to_decimal_latex(frac_as_decimal)
        return frac_as_decimal, decimal_latex
    
    def _make_random_integer(self, max_num=6, min_num=-6):
        """ランダムな整数を作成する

        Args:
            max_num (int, optional): 値の最大値
            min_num (int, optional): 値の最小値

        Returns:
            integer (sy.Integer): 計算に用いる整数
            integer_latex (str): 表示に用いる整数
        """
        checker = random()
        if checker > 0.5:
            numerator = randint(1, max_num)
        else:
            numerator = randint(min_num, -1)
        
        integer = sy.Integer(numerator)
        integer_latex = sy.latex(integer)
        return integer, integer_latex
    
    def _is_finite_decimal(self, rational_number):
        """有限小数か否かを判定

        Args:
            rational_number (sy.Rational): 判定したい分数

        Returns:
            (bool): 有限小数ならTrue, 無限小数ならFalse
        """
        denominator_list = list(sy.factorint(rational_number.denominator).keys())
        denominator_set = set(denominator_list)
        if denominator_set == set():
            return True
        elif denominator_set == {2}:
            return True
        elif denominator_set == {5}:
            return True
        elif denominator_set == {2, 5}:
            return True
        else:
            return False
