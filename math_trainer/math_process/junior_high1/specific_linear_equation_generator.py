from random import choice, randint, random, sample, shuffle

import sympy as sy


from math_trainer.math_process.base_generator import BaseProblemGenerator

class SpecificLinearEquationGenerator(BaseProblemGenerator):
    """特定の形を持つ1次方程式の解を求める問題を出力する
    
    Args:
        BaseProblemGenerator: 全体に共通する問題の設定
    
    Attributes:
        numbers_to_use (list): 係数に利用する数字のタイプを格納する
        problem_types (list): 問題に出力される1次方程式の形を格納する
        choices (list[str]): 問題の選択肢。正解が1つで偽答が3つ
        latex_answer (str): latex形式で記述された解答
        latex_problem (str): latex形式で記述された問題
    
    Note:
        解としては基本的に整数、分数が優先されて、小数だけが選択されているときに例外的に小数へと変換される
        また、解とつじつま合わせをするために計算されて出てくる係数も、同様の仕様となっている。
    """
    def __init__(self, **settings: dict):
        """初期化
        
        Args:
            settings (dict): 問題の設定が格納されている
        """
        super().__init__(**settings)
        sy.init_printing(order='grevlex')
        self.numbers_to_use = settings['numbers_to_use']
        self.problem_types = settings['problem_types']
    
    def _build_one(self):
        """選択された1次方程式の形に応じて、1問単位の問題と解答を出力する
        
        Returns:
            latex_answer (str): latex形式で記述された解答
            latex_problem (str): latex形式で記述されたされた問題
        """
        problem_text = ""
        answer_text = ""
        choices = []

        selected_problem_type = choice(self.problem_types)
        if selected_problem_type == "ax_equal_b_only_integer":
            # latex_answer, latex_problem = self._make_ax_equal_b_only_integer()
            answer_text, problem_text, choices = self._make_ax_equal_b_only_integer()
        elif selected_problem_type == "ax_equal_b_all_number":
            answer_text, problem_text, choices = self._make_ax_equal_b_all_number()
        elif selected_problem_type == 'ax_plus_b_equal_c_only_integer':
            answer_text, problem_text, choices = self._make_ax_plus_b_equal_c_only_integer()
        elif selected_problem_type == 'ax_plus_b_equal_c_all_number':
            answer_text, problem_text, choices = self._make_ax_plus_b_equal_c_all_number()
        elif selected_problem_type == 'ax_plus_b_equal_cx_plus_d_only_integer':
            answer_text, problem_text, choices = self._make_ax_plus_b_equal_cx_plus_d_only_integer()
        elif selected_problem_type == 'ax_plus_b_equal_cx_plus_d_all_number':
            answer_text, problem_text, choices = self._make_ax_plus_b_equal_cx_plus_d_all_number()
        else:
            raise ValueError(f"Unexpected selected_problem_type: {selected_problem_type}")
        return {
            "problem_text": problem_text,
            "answer_text": answer_text,
            "choices": choices,
            "metadata": {},
        }
    
    def generate(self):
        return self._build_one()
        
    def _make_ax_equal_b_only_integer(self) -> tuple[str, str, list[str]]:
        """ax=b型(整数解)の1次方程式を作成

        Returns:
            latex_answer (str): latex形式で記述された解答
            latex_problem (str): latex形式で記述された問題
            choices (list[str]): 正答と誤答がlatex形式で記述された選択肢軍
        """
        def _latex_int(n):
            """
            細かい数の条件に応じて確実にlatex化できるような動作
            """
            # n が int/sympy のどちらでも整数としてLaTeX化
            if isinstance(n, int):
                return sy.latex(sy.Integer(n))
            if isinstance(n, sy.Rational) and n.q == 1:
                return sy.latex(n)  # 既に整数
            if isinstance(n, sy.Integer):
                return sy.latex(n)
            # 念のため整数化できるケース
            return sy.latex(sy.Integer(int(n)))

        def make_dummy_choices(a, b):
            """
            ax=bのa,bからダミー用の値を3つ作成
            
            Args:
                a, b (sy.Integer | sy.Rational | sy.Float): 1次方程式のxの係数、および右辺にある定数
            
            Returns:
                dummies: answerと重複しない3つのダミー値とそのlatex
                
            Developing:
                解は整数であること
                同じ値にはならないこと
            """            
            answer = sy.Rational(b, a)
            dummies = set()
            # ありそうな誤答からの選択
            # x = a / b
            if b != 0:
                dummy = sy.Rational(a, b)
                if (dummy != answer) and (dummy.is_integer):
                    dummies.add(dummy)
            # x = b - a
            dummy = b - a
            if (dummy != answer) and (dummy.is_integer):
                dummies.add(dummy)
            # x = a * b
            dummy = a * b
            if (dummy != answer) and (dummy.is_integer):
                dummies.add(dummy)
            # x = b
            dummy = b
            if (dummy != answer) and (dummy.is_integer):
                dummies.add(dummy)
            # x = - b / a
            dummy = -sy.Rational(b, a)
            if (dummy != answer) and (dummy.is_integer):
                dummies.add(dummy)
            # 近傍の値

            # 2) 近傍（±1..±5）
            for d in (1, 2, 3, 4, 5):
                for cand in (answer + d, answer - d):
                    if cand != answer and cand.is_integer:
                        dummies.add(cand)

            # 3) フォールバック（決定的に埋める）
            if len(dummies) < 3:
                for k in range(-50, 51):
                    if k == int(answer):  # 真値は除外
                        continue
                    dummies.add(sy.Integer(k))
                    if len(dummies) >= 3:
                        break

            # 偽答が3つにならない場合の妥協ランダム
            if len(dummies) < 3:
                for number in range(-10, 10):
                    number = sy.Integer(number)
                    if (number != answer) and (number.is_integer):
                        dummies.add(number)
                    if len(dummies) >= 3:
                        break

            dummies = list(dummies)
            selected_dummies = sample(dummies, 3)
            return selected_dummies

        answer, answer_latex = self._make_random_number(number_type="integer")
        latex_answer = f"\( x = {answer_latex} \)"
        
        while True:
            a, a_latex = self._make_random_number()
            if (a != 1) and (a != 0):
                break
        
        b =  a * answer
        if ("decimal" in self.numbers_to_use) and ("frac" not in self.numbers_to_use) and ("integer" not in self.numbers_to_use):
            b_latex = sy.latex(sy.Float(b))
        else:
            b_latex = sy.latex(b)
        
        if a == -1:
            latex_problem = f"\( -x = {b_latex} \)"
        else:
            latex_problem = f"\( {a_latex}x = {b_latex} \)"
            
        # 偽答作成
        dummy_answers = make_dummy_choices(a, b)
        choices = [latex_answer]
        for d in dummy_answers:
            choices.append(f"\( x = {_latex_int(d)} \)")

        shuffle(choices)
        return latex_answer, latex_problem, choices

    def _make_ax_equal_b_all_number(self) -> tuple[str, str, list[str]]:
        """ax=b型(分数・小数解含む)の一次方程式を作成（choices付き）"""

        # ---- モード判定（小数のみ？） ----
        decimal_only = ("decimal" in self.numbers_to_use) and ("frac" not in self.numbers_to_use) and ("integer" not in self.numbers_to_use)

        # ---- 小数(十分位)化（Rational -> 10分の1単位に丸め） ----
        def to_tenth(x: sy.Rational) -> sy.Rational:
            # xはRational/Integer想定。最近似の1/10単位に四捨五入
            # round(x*10)/10 を Rational で実現
            n10 = sy.Integer(sy.floor(x*10 + sy.Rational(1,2)))  # 四捨五入
            return sy.Rational(n10, 10)

        # ---- 表示用LaTeX ----
        def fmt_for_choice(x: sy.Rational) -> str:
            if decimal_only:
                # 十分位で表示（必ず1桁小数）
                x10 = to_tenth(x)
                return sy.latex(sy.Float(x10))  # 例: 1.2 のように出力される
            else:
                # 分数/整数はそのままのLaTeX（Rationalは既約で出る）
                return sy.latex(x)

        # ---- 誤答生成（ax=b 用；answerは RATIONAL のまま扱う） ----
        def make_dummy_choices_all(a: sy.Rational, b: sy.Rational, answer: sy.Rational) -> list[sy.Rational]:
            pool = set()

            # 1) 典型ミス（ゼロ除算等は防御）
            # x = a / b
            if b != 0:
                cand = sy.Rational(a, b)
                if cand != answer:
                    pool.add(cand)
            # x = b - a
            cand = b - a
            if cand != answer:
                pool.add(cand)
            # x = a * b
            cand = a * b
            if cand != answer:
                pool.add(cand)
            # x = b （割り忘れ）
            cand = b
            if cand != answer:
                pool.add(cand)
            # x = - b / a
            cand = -sy.Rational(b, a)  # a≠0 は生成側で保証
            if cand != answer:
                pool.add(cand)
            # 符号反転（よくある取り違え）
            cand = -answer
            if cand != answer:
                pool.add(cand)

            # 2) 近傍候補
            if decimal_only:
                # 十分位で ±0.1, ±0.2, ±0.3 を用意
                for k in (1, 2, 3):
                    for s in (1, -1):
                        cand = answer + s * sy.Rational(k, 10)
                        if cand != answer:
                            pool.add(cand)
                # 切り上げ・切り捨て（十分位）
                pool.add(sy.Rational(sy.floor(answer*10), 10))
                pool.add(sy.Rational(sy.ceiling(answer*10), 10))
                # 桁ズレ（×10, ÷10 を十分位に丸め直して使う）
                pool.add(to_tenth(answer*10))
                if answer != 0:
                    pool.add(to_tenth(answer/10))
            else:
                # 分数近傍（±1/q）
                for q in (2, 3, 4, 5, 6):
                    for s in (1, -1):
                        cand = answer + s * sy.Rational(1, q)
                        if cand != answer:
                            pool.add(cand)
                # 分子・分母に±1（Rationalにしてから）
                ans = sy.Rational(answer)  # IntegerもRational化
                p, q = ans.p, ans.q
                for dp in (-1, 1):
                    pool.add(sy.Rational(p+dp, q))
                for dq in (-1, 1):
                    if (q + dq) != 0:
                        pool.add(sy.Rational(p, q+dq))
                # 逆数（0除外）
                if answer != 0:
                    pool.add(sy.Rational(1, answer))

            # 真値除外（decimal-onlyの場合は十分位丸め一致も除外）
            if decimal_only:
                ans10 = to_tenth(answer)
                pool = {to_tenth(c) for c in pool if to_tenth(c) != ans10}
            else:
                pool = {c for c in pool if c != answer}

            # 3) フォールバック（決定的に埋める）
            need = 3 - len(pool)
            if need > 0:
                if decimal_only:
                    # 十分位の等差列（answer近傍）で埋める
                    base = sy.Integer(sy.floor(answer*10))
                    extras = []
                    for d in range(1, 30):  # ±3.0 まで十分
                        for s in (1, -1):
                            n = base + s*d
                            extras.append(sy.Rational(n, 10))
                            if len(extras) >= need:
                                break
                        if len(extras) >= need:
                            break
                    for e in extras:
                        if e != to_tenth(answer):
                            pool.add(e)
                else:
                    # 小分子・小分母の有理数で埋める
                    extras = []
                    for num in range(-5, 6):
                        for den in range(2, 7):
                            if den == 0:
                                continue
                            r = sy.Rational(num, den)
                            if r != answer:
                                extras.append(r)
                            if len(extras) >= need:
                                break
                        if len(extras) >= need:
                            break
                    pool.update(extras[:need])

            # 4) 3つランダム抽出
            pool = list(pool)
            shuffle(pool)
            return pool[:3]

        # ---- 正答を作成（小数onlyならdecimal、そうでなければ frac/integer） ----
        if decimal_only:
            answer, answer_latex = self._make_random_number(number_type="decimal")
        else:
            answer, answer_latex = self._make_random_number(number_type=choice(["frac", "integer"]))

        latex_answer = f"\( x = {answer_latex} \)"

        # a（0,1以外）を選ぶ
        while True:
            a, a_latex = self._make_random_number()
            if (a != 1) and (a != 0):
                break

        # b を構成（表示規則は既存どおり）
        b = a * answer
        if decimal_only:
            b_latex = sy.latex(sy.Float(b))
        else:
            b_latex = sy.latex(b)

        # 問題式
        if a == -1:
            latex_problem = f"\( -x = {b_latex} \)"
        else:
            latex_problem = f"\( {a_latex}x = {b_latex} \)"

        # ---- 選択肢（正答 + ダミー3） ----
        true_answer = sy.Rational(b, a)  # RATIONALで保持
        dummies = make_dummy_choices_all(a, b, true_answer)

        choices = [latex_answer]
        for d in dummies:
            choices.append(f"\( x = {fmt_for_choice(d)} \)")
        shuffle(choices)

        return latex_answer, latex_problem, choices


    def _make_ax_plus_b_equal_c_only_integer(self):
        """ax+b=c型(整数解)の1次方程式を作成

        Returns:
            latex_answer (str): latex形式で記述された解答
            latex_problem (str): latex形式で記述された問題
            choices (list[str])
        """
        def is_int(number) -> bool:
            if isinstance(number, sy.Integer):
                return True
            elif isinstance(number, int):
                return True
            else:
                return False
        
        def _latex_int(n):
            """
            細かい数の条件に応じて確実にlatex化できるような動作
            """
            # n が int/sympy のどちらでも整数としてLaTeX化
            if isinstance(n, int):
                return sy.latex(sy.Integer(n))
            if isinstance(n, sy.Rational) and n.q == 1:
                return sy.latex(n)  # 既に整数
            if isinstance(n, sy.Integer):
                return sy.latex(n)
            # 念のため整数化できるケース
            return sy.latex(sy.Integer(int(n)))
        
        def make_dummy_choices(a, b, c):
            """
            ax + b = cのa, b, cからダミー用の値を3つ作成
            
            Args:
                a, b, c (sy.Integer | sy.Rational | sy.Float): 1次方程式のxの係数、左辺にある定数、右辺にある定数
            
            Returns:
                dummies (list[str]): answerと重複しない3つのダミー値とそのlatex
                
            Developing:

            """            
            answer = sy.Rational(c - b, a)
            dummies = set()
            # ありそうな誤答からの選択
            probable_wrong_answers = []
            
            if a != 0:
                # 移項の際の符号ミス
                probable_wrong_answers.append(sy.Rational(c + b, a))
                # 移項と除算を混同
                probable_wrong_answers.append(sy.Rational(c - b, -a))
                # 移項の際の符号ミス+勝手に符号変更
                probable_wrong_answers.append(sy.Rational(b - c, a))
                # 勝手に絶対値化(符号アレルギー)
                probable_wrong_answers.append(sy.Rational(sy.Abs(c - b), a))
                # aを割り算しているのに移項まで行っている
                probable_wrong_answers.append(sy.Rational(c - b, a) + a)
                probable_wrong_answers.append(sy.Rational(c - b, a) - a)

            # a + bを係数と勘違い
            if (a + b) != 0:
                probable_wrong_answers.append(sy.Rational(c, a + b))

            # a除算忘れ
            probable_wrong_answers.append(c - b)
            # aを定数と混同
            probable_wrong_answers.append(c - b - a)
            # 除算と乗算の勘違い
            probable_wrong_answers.append(a * (c - b))
            # 係数の判断ミス＋移項
            probable_wrong_answers.append(c - (a + b))

            for wrong_answer in probable_wrong_answers:
                if (is_int(wrong_answer)) and (wrong_answer != answer):
                    dummies.add(wrong_answer)
        
            # 2) 近傍（±1..±5）
            for d in (1, 2, 3, 4, 5):
                for cand in (answer + d, answer - d):
                    if cand != answer and is_int(cand):
                        dummies.add(cand)

            # 3) フォールバック（決定的に埋める）
            if len(dummies) < 3:
                for k in range(-50, 51):
                    if k == int(answer):  # 真値は除外
                        continue
                    dummies.add(sy.Integer(k))
                    if len(dummies) >= 3:
                        break

            # 偽答が3つにならない場合の妥協ランダム
            if len(dummies) < 3:
                for number in range(-10, 10):
                    number = sy.Integer(number)
                    if (number != answer) and (is_int(number)):
                        dummies.add(number)
                    if len(dummies) >= 3:
                        break

            dummies = list(dummies)
            selected_dummies = sample(dummies, 3)
            return selected_dummies
        
        answer, answer_latex = self._make_random_number(number_type="integer")
        latex_answer = f"\( x = {answer_latex} \)"
        while True:
            a, a_latex = self._make_random_number()
            if a != 0:
                break
        c, c_latex = self._make_random_number()
        b = c - a * answer
        
        if ("decimal" in self.numbers_to_use) and ("frac" not in self.numbers_to_use) and ("integer" not in self.numbers_to_use):
            b_latex = sy.latex(sy.Float(b))
        else:
            b_latex = sy.latex(b)
        
        latex_problem = "\( "
        # a add part
        if a == 1:
            latex_problem += "x"
        elif a == -1:
            latex_problem += "-x"
        else:
            latex_problem += f"{a_latex}x"
        # b add part
        if b == 0:
            pass
        elif b > 0:
            latex_problem += f"+ {b_latex}"
        else:
            latex_problem += f"{b_latex}"
        # c add part
        latex_problem += f"= {c_latex} \)"
        
        choices = [latex_answer]
        dummy_answers = make_dummy_choices(a, b, c)
        for dummy_answer in dummy_answers:
            choices.append(f"\(x = {_latex_int(dummy_answer)} \)")
        shuffle(choices)
        return latex_answer, latex_problem, choices

    def _make_ax_plus_b_equal_c_all_number(self):
        """ax+b=c型(分数解含む)の1次方程式を作成

        Returns:
            latex_answer (str): latex形式で記述された解答
            latex_problem (str): latex形式で記述された問題
            choices (list[str]): 正答と偽答を含む4つの選択肢
        """
        decimal_only = ("decimal" in self.numbers_to_use) and ("frac" not in self.numbers_to_use) and ("integer" not in self.numbers_to_use)

        # ---- 小数(十分位)化（Rational -> 10分の1単位に丸め） ----
        def to_tenth(x: sy.Rational) -> sy.Rational:
            # xはRational/Integer想定。最近似の1/10単位に四捨五入
            # round(x*10)/10 を Rational で実現
            n10 = sy.Integer(sy.floor(x*10 + sy.Rational(1,2)))  # 四捨五入
            return sy.Rational(n10, 10)

        # ---- 表示用LaTeX ----
        def fmt_for_choice(x: sy.Rational) -> str:
            if decimal_only:
                # 十分位で表示（必ず1桁小数）
                x10 = to_tenth(x)
                return sy.latex(sy.Float(x10))  # 例: 1.2 のように出力される
            else:
                # 分数/整数はそのままのLaTeX（Rationalは既約で出る）
                return sy.latex(x)

        def make_dummy_choices_all(a, b, c, answer) -> list[sy.Rational]:
            pool = set()
            # ありそうな誤答からの選択
            probable_wrong_answers = []
            
            if a != 0:
                # 移項の際の符号ミス
                probable_wrong_answers.append(sy.Rational(c + b, a))
                # 移項と除算を混同
                probable_wrong_answers.append(sy.Rational(c - b, -a))
                # 移項の際の符号ミス+勝手に符号変更
                probable_wrong_answers.append(sy.Rational(b - c, a))
                # 勝手に絶対値化(符号アレルギー)
                probable_wrong_answers.append(sy.Rational(sy.Abs(c - b), a))
                # aを割り算しているのに移項まで行っている
                probable_wrong_answers.append(sy.Rational(c - b, a) + a)
                probable_wrong_answers.append(sy.Rational(c - b, a) - a)

            # a + bを係数と勘違い
            if (a + b) != 0:
                probable_wrong_answers.append(sy.Rational(c, a + b))

            # a除算忘れ
            probable_wrong_answers.append(c - b)
            # aを定数と混同
            probable_wrong_answers.append(c - b - a)
            # 除算と乗算の勘違い
            probable_wrong_answers.append(a * (c - b))
            # 係数の判断ミス＋移項
            probable_wrong_answers.append(c - (a + b))

            for wrong_answer in probable_wrong_answers:
                if wrong_answer != answer:
                    pool.add(wrong_answer)

            # 2) 近傍候補
            if decimal_only:
                # 十分位で ±0.1, ±0.2, ±0.3 を用意
                for k in (1, 2, 3):
                    for s in (1, -1):
                        cand = answer + s * sy.Rational(k, 10)
                        if cand != answer:
                            pool.add(cand)
                # 切り上げ・切り捨て（十分位）
                pool.add(sy.Rational(sy.floor(answer*10), 10))
                pool.add(sy.Rational(sy.ceiling(answer*10), 10))
                # 桁ズレ（×10, ÷10 を十分位に丸め直して使う）
                pool.add(to_tenth(answer*10))
                if answer != 0:
                    pool.add(to_tenth(answer/10))
            else:
                # 分数近傍（±1/q）
                for q in (2, 3, 4, 5, 6):
                    for s in (1, -1):
                        cand = answer + s * sy.Rational(1, q)
                        if cand != answer:
                            pool.add(cand)
                # 分子・分母に±1（Rationalにしてから）
                ans = sy.Rational(answer)  # IntegerもRational化
                p, q = ans.p, ans.q
                for dp in (-1, 1):
                    pool.add(sy.Rational(p+dp, q))
                for dq in (-1, 1):
                    if (q + dq) != 0:
                        pool.add(sy.Rational(p, q+dq))
                # 逆数（0除外）
                if answer != 0:
                    pool.add(sy.Rational(1, answer))

            # 真値除外（decimal-onlyの場合は十分位丸め一致も除外）
            if decimal_only:
                ans10 = to_tenth(answer)
                pool = {to_tenth(c) for c in pool if to_tenth(c) != ans10}
            else:
                pool = {c for c in pool if c != answer}

            # 3) フォールバック（決定的に埋める）
            need = 3 - len(pool)
            if need > 0:
                if decimal_only:
                    # 十分位の等差列（answer近傍）で埋める
                    base = sy.Integer(sy.floor(answer*10))
                    extras = []
                    for d in range(1, 30):  # ±3.0 まで十分
                        for s in (1, -1):
                            n = base + s*d
                            extras.append(sy.Rational(n, 10))
                            if len(extras) >= need:
                                break
                        if len(extras) >= need:
                            break
                    for e in extras:
                        if e != to_tenth(answer):
                            pool.add(e)
                else:
                    # 小分子・小分母の有理数で埋める
                    extras = []
                    for num in range(-5, 6):
                        for den in range(2, 7):
                            if den == 0:
                                continue
                            r = sy.Rational(num, den)
                            if r != answer:
                                extras.append(r)
                            if len(extras) >= need:
                                break
                        if len(extras) >= need:
                            break
                    pool.update(extras[:need])

            # 4) 3つランダム抽出
            pool = list(pool)
            shuffle(pool)
            return pool[:3]

        if decimal_only:
            answer, answer_latex = self._make_random_number(number_type="decimal")
        else:
            answer, answer_latex = self._make_random_number(number_type=choice(["frac", "integer"]))
        latex_answer = f"\( x = {answer_latex} \)"
        
        while True:
            a, a_latex = self._make_random_number()
            if a != 0:
                break
        c, c_latex = self._make_random_number()
        b = c - a * answer
        
        if decimal_only:
            b_latex = sy.latex(sy.Float(b))
        else:
            b_latex = sy.latex(b)
        
        latex_problem = "\( "
        # a add part
        if a == 1:
            latex_problem += "x"
        elif a == -1:
            latex_problem += "-x"
        else:
            latex_problem += f"{a_latex}x"
        # b add part
        if b == 0:
            pass
        elif b > 0:
            latex_problem += f"+ {b_latex}"
        else:
            latex_problem += f"{b_latex}"
        # c add part
        latex_problem += f"= {c_latex} \)"
        
        choices = [latex_answer]
        dummies = make_dummy_choices_all(a, b, c, answer)
        for dummy in dummies:
            choices.append(f"\( x = {fmt_for_choice(dummy)} \)")
        shuffle(choices)
        return latex_answer, latex_problem, choices

    def _make_ax_plus_b_equal_cx_plus_d_only_integer(self):
        """ax+b=cx+d型(整数解のみ)の1次方程式を作成

        Returns:
            latex_answer (str): latex形式で記述された解答
            latex_problem (str): latex形式で記述された問題
            choices (list[str]): 正答1つ誤答3つを含む選択肢群
        """
        decimal_only = ("decimal" in self.numbers_to_use) and ("frac" not in self.numbers_to_use) and ("integer" not in self.numbers_to_use)
        
        def _latex_int(n):
            """
            細かい数の条件に応じて確実にlatex化できるような動作
            """
            # n が int/sympy のどちらでも整数としてLaTeX化
            if isinstance(n, int):
                return sy.latex(sy.Integer(n))
            if isinstance(n, sy.Rational) and n.q == 1:
                return sy.latex(n)  # 既に整数
            if isinstance(n, sy.Integer):
                return sy.latex(n)
            # 念のため整数化できるケース
            return sy.latex(sy.Integer(int(n)))
        
        def make_dummy_choices(a, b, c, d, answer):
            """
            ax + b = cx + d のダミー（整数）を3つ返す。
            Args:
                a, b, c, d: Sympyの Integer/Rational を想定（Floatは非推奨）
                answer: 真の解。整数（Sympy Integer か、分母1の Rational）前提。
            """
            # ---- ユーティリティ ----
            def is_int_like(x) -> bool:
                """整数型と扱えるかどうかの判定

                Args:
                    x (int | sy.Integer | sy.Rational | sy.Float): 判定対象

                Returns:
                    bool: 整数であるか否か
                """
                # int, sy.Integerは真
                if isinstance(x, (int, sy.Integer)):
                    return True
                # sy.Rationalでも分母が1
                if isinstance(x, sy.Rational) and x.q == 1:
                    return True
                # 念の為のis_integer持ちかどうか
                return getattr(x, "is_integer", None) is True

            def to_sympy_int(x) -> sy.Integer:
                """整数をsympy基準のものに切り替えるヘルパー関数

                Args:
                    x : 対象の数

                Raises:
                    ValueError: int化できないものが来た時に送出

                Returns:
                    sy.Integer: 変換された整数
                """
                if isinstance(x, sy.Integer):
                    return x
                if isinstance(x, int):
                    return sy.Integer(x)
                if isinstance(x, sy.Rational) and x.q == 1:
                    return sy.Integer(x.p)
                raise ValueError(f"Non-integer candidate: {x!r}")

            MAX_ABS = 10**2  # 巨大値ガード

            def safe_add(candidate, pool: set, true_ans: sy.Integer):
                """ダミーの候補を安全に追加する

                Args:
                    candidate: 加えられる可能性のある数 
                    pool (set): 候補を格納する集合
                    true_ans (sy.Integer): その問題の方程式の解答
                """
                # そもそも候補が存在しないとき
                if candidate is None:
                    return
                try:
                    # そもそも整数型にはできないもののとき
                    if not is_int_like(candidate):
                        return
                    ci = to_sympy_int(candidate)
                    # 整数化はできたが、値があまりにも大きい時
                    if abs(ci) > MAX_ABS:
                        return
                    # いずれも問題ないとき
                    if ci != true_ans and ci not in pool:
                        pool.add(ci)
                except Exception:
                    return

            # ---- 真値の整合チェック ----
            true_answer_expr = sy.Rational(d - b, a - c)  # 数式としての真値
            assert is_int_like(answer)
            true_answer = to_sympy_int(answer)

            # 数式真値と渡された真値が一致するか（型ブレ検出用）
            # 等価（例：3 == 6/2）ならOK
            if true_answer_expr != true_answer:
                # 等価チェック（簡易）
                if not is_int_like(true_answer_expr) or to_sympy_int(true_answer_expr) != true_answer:
                    raise ValueError("answer != (d-b)/(a-c)")

            # ---- 典型誤答候補 ----
            pool = set()
            candidates = []

            # 符号ミス（片側/両方）
            candidates.append(sy.Rational(d + b, a - c))
            candidates.append(sy.Rational(d - b, a + c))
            candidates.append(sy.Rational(d + b, a + c))

            # 除算忘れ
            candidates.append(d - b)

            # 分母を a/c にする
            if a != 0:
                candidates.append(sy.Rational(d - b, a))
            if c != 0:
                candidates.append(sy.Rational(d - b, c))

            # 反転・向き違い
            candidates.append(sy.Rational(b - d, a - c))   # 分子逆
            candidates.append(sy.Rational(d - b, c - a))   # 分母逆
            # (b - d)/(c - a) は真値と一致するので、後の等価除外で落ちる

            # 逆数
            if (d - b) != 0:
                candidates.append(sy.Rational(a - c, d - b))

            # 絶対値
            candidates.append(sy.Rational(sy.Abs(d - b), a - c))
            if (a - c) != 0:
                candidates.append(sy.Rational(d - b, sy.Abs(a - c)))

            # 1) まずは典型ミスから詰める
            for cand in candidates:
                # 真値と等価（例：(b-d)/(c-a)）のものは safe_add が弾く
                safe_add(cand, pool, true_answer)

            # 2) 近傍（±1..±5）
            for dlt in (1, 2, 3, 4, 5):
                safe_add(true_answer + dlt, pool, true_answer)
                safe_add(true_answer - dlt, pool, true_answer)
                if len(pool) >= 8:
                    break

            # 3) フォールバック
            if len(pool) < 3:
                t = int(true_answer)
                delta = 1
                while len(pool) < 3 and delta <= 50:
                    safe_add(sy.Integer(t + delta), pool, true_answer)
                    safe_add(sy.Integer(t - delta), pool, true_answer)
                    delta += 1

            pool = list(pool)
            if len(pool) >= 3:
                return sample(pool, 3)
            # 最終保険（ほぼ到達しない）
            while len(pool) < 3:
                pool.append(true_answer + len(pool) + 1)
            return pool[:3]


        answer, answer_latex = self._make_random_number(number_type="integer")
        latex_answer = f"\( x = {answer_latex} \)"
        while True:
            a, a_latex = self._make_random_number()
            c, c_latex = self._make_random_number()
            if (a != 0) and (c != 0) and (a != c):
                break 
        
        if random() > 0.5:
            b, b_latex = self._make_random_number()
            d = a * answer + b - c * answer
            if decimal_only:
                d_latex = sy.latex(sy.Float(d))
            else:
                d_latex = sy.latex(d)
        else:
            d, d_latex = self._make_random_number()
            b = -1 * a * answer + c * answer + d
            if decimal_only:
                b_latex = sy.latex(sy.Float(b))
            else:
                b_latex = sy.latex(b)
        
        latex_problem = "\( "
        # a add part
        if a == 1:
            latex_problem += "x"
        elif a == -1:
            latex_problem += "-x"
        else:
            latex_problem += f"{a_latex}x"
        # b add part
        if b == 0:
            pass
        elif b > 0:
            latex_problem += f"+ {b_latex}"
        else:
            latex_problem += f"{b_latex}"
        # c add part
        if c == 1:
            latex_problem += "= x"
        elif c == -1:
            latex_problem += "= -x"
        else:
            latex_problem += f"= {c_latex}x"
        # d add part
        if d == 0:
            pass
        elif d > 0:
            latex_problem += f"+ {d_latex}"
        else:
            latex_problem += f"{d_latex}"
        latex_problem += " \)"
        
        choices = [latex_answer]
        dummy_choices = make_dummy_choices(a, b, c, d, answer)
        for dummy in dummy_choices:
            choices.append(f"\( x = {_latex_int(dummy)} \)")
        shuffle(choices)        
        return latex_answer, latex_problem, choices

    def _make_ax_plus_b_equal_cx_plus_d_all_number(self):
        """ax+b=cx+d型(分数解含む)の1次方程式を作成
        
        Returns:
            latex_answer (str): latex形式で記述された解答
            latex_problem (str): latex形式で記述された問題
            choices (list[str]): 正答と偽答を含む4つの選択肢
        """
        is_decimal_only = ("decimal" in self.numbers_to_use) and ("frac" not in self.numbers_to_use) and ("integer" not in self.numbers_to_use)

        # ---- 小数(十分位)化（Rational -> 10分の1単位に丸め） ----
        def to_tenth(x: sy.Rational) -> sy.Rational:
            # xはRational/Integer想定。最近似の1/10単位に四捨五入
            # round(x*10)/10 を Rational で実現
            n10 = sy.Integer(sy.floor(x*10 + sy.Rational(1,2)))  # 四捨五入
            return sy.Rational(n10, 10)

        # ---- 表示用LaTeX ----
        def fmt_for_choice(x: sy.Rational) -> str:
            if is_decimal_only:
                # 十分位で表示（必ず1桁小数）
                x10 = to_tenth(x)
                return sy.latex(sy.Float(x10))  # 例: 1.2 のように出力される
            else:
                # 分数/整数はそのままのLaTeX（Rationalは既約で出る）
                return sy.latex(x)

        def make_dummy_choices_all(a, b, c, d, answer):
            """
            誤答作成用メソッド
            Args:
                a, b, c, d: ax + b = cx + d の係数（Sympy Integer/Rational）
                answer: 真の解（Sympy Integer/Rational）
            Returns:
                list[sy.Rational]: ダミー候補3つ
            """
            # ▼ 真値の整合を検証（型ブレ検知）
            true_expr = sy.Rational(d - b, a - c)  # a != c は呼び出し側で担保済み
            assert sy.Rational(answer) == true_expr, "answer != (d-b)/(a-c)"

            # ▼ 安全追加ヘルパ（巨大値・真値・重複を排除）
            MAX_ABS = 10**6
            pool: set[sy.Rational] = set()

            def safe_add(x):
                if x is None:
                    return
                try:
                    xr = sy.Rational(x)  # Integer も Rational 化（既約になる）
                except Exception:
                    return
                if abs(xr) > MAX_ABS:
                    return
                if xr != true_expr:
                    pool.add(xr)

            # ▼ 典型誤答
            # 符号ミス（片/両）
            if (a + c) != 0:
                safe_add(sy.Rational(d - b, a + c))
                safe_add(sy.Rational(d + b, a + c))
            safe_add(sy.Rational(d + b, a - c))          # a-c は非ゼロ
            # 係数と定数の混同
            safe_add(c + d - b - a)
            if a != 0:
                safe_add(sy.Rational(c + d - b, a))
            # (a+b) を係数と思う
            if (a + b) != 0:
                safe_add(sy.Rational(c + d, a + b))
            # 除算忘れ
            safe_add(d - b)
            # 乗除混同
            safe_add((d - b) * (c - a))
            # 分子分母の反転
            if (d - b) != 0:
                safe_add(sy.Rational(a - c, d - b))

            # ▼ 近傍
            if is_decimal_only:
                for k in (1, 2, 3):
                    safe_add(answer + sy.Rational(k, 10))
                    safe_add(answer - sy.Rational(k, 10))
                safe_add(sy.Rational(sy.floor(answer*10), 10))
                safe_add(sy.Rational(sy.ceiling(answer*10), 10))
                safe_add(to_tenth(answer*10))
                if answer != 0:
                    safe_add(to_tenth(answer/10))
                # 真値（十分位一致）を除外
                ans10 = to_tenth(answer)
                pool = {to_tenth(x) for x in pool if to_tenth(x) != ans10}
            else:
                # ±1/den
                for den in (2, 3, 4, 5, 6):
                    safe_add(answer + sy.Rational(1, den))
                    safe_add(answer - sy.Rational(1, den))
                # 分子・分母 ±1
                ans_r = sy.Rational(answer)
                p_num, q_den = ans_r.p, ans_r.q
                safe_add(sy.Rational(p_num + 1, q_den)); safe_add(sy.Rational(p_num - 1, q_den))
                if (q_den + 1) != 0: safe_add(sy.Rational(p_num, q_den + 1))
                if (q_den - 1) != 0: safe_add(sy.Rational(p_num, q_den - 1))
                # 逆数
                if answer != 0:
                    safe_add(sy.Rational(1, answer))
                # 真値除外
                pool = {x for x in pool if x != true_expr}

            # ▼ フォールバック（不足分を埋める）
            need = 3 - len(pool)
            if need > 0:
                if is_decimal_only:
                    base = sy.Integer(sy.floor(answer*10))
                    extras = []
                    for step in range(1, 30):
                        extras.append(sy.Rational(base + step, 10))
                        extras.append(sy.Rational(base - step, 10))
                        if len(extras) >= need:
                            break
                    for e in extras[:need]:
                        if e != to_tenth(answer):
                            pool.add(e)
                else:
                    extras = []
                    for num in range(-5, 6):
                        for den in range(2, 7):
                            r = sy.Rational(num, den)
                            if r != true_expr:
                                extras.append(r)
                            if len(extras) >= need:
                                break
                        if len(extras) >= need:
                            break
                    for e in extras[:need]:
                        pool.add(e)

            pool = list(pool)
            shuffle(pool)
            return pool[:3]



        if is_decimal_only:
            answer, answer_latex = self._make_random_number(number_type="decimal")
        else:
            answer, answer_latex = self._make_random_number(number_type=choice(["frac", "integer"]))
        latex_answer = f"\( x = {answer_latex} \)"
        while True:
            a, a_latex = self._make_random_number()
            c, c_latex = self._make_random_number()
            if (a != 0) and (c != 0) and (a != c):
                break 

        if random() > 0.5:
            b, b_latex = self._make_random_number()
            d = a * answer + b - c * answer
            if is_decimal_only:
                d_latex = sy.latex(sy.Float(d))
            else:
                d_latex = sy.latex(d)
        else:
            d, d_latex = self._make_random_number()
            b = -1 * a * answer + c * answer + d
            if is_decimal_only:
                b_latex = sy.latex(sy.Float(b))
            else:
                b_latex = sy.latex(b)
        
        latex_problem = "\( "
        # a add part
        if a == 1:
            latex_problem += "x"
        elif a == -1:
            latex_problem += "-x"
        else:
            latex_problem += f"{a_latex}x"
        # b add part
        if b == 0:
            pass
        elif b > 0:
            latex_problem += f"+ {b_latex}"
        else:
            latex_problem += f"{b_latex}"
        # c add part
        if c == 1:
            latex_problem += "= x"
        elif c == -1:
            latex_problem += "= -x"
        else:
            latex_problem += f"= {c_latex}x"
        # d add part
        if d == 0:
            pass
        elif d > 0:
            latex_problem += f"+ {d_latex}"
        else:
            latex_problem += f"{d_latex}"
        latex_problem += " \)"
        

        choices = [f"\\( x = {fmt_for_choice(answer)} \\)"]   # ← 正答も fmt_for_choice 経由で
        dummies = make_dummy_choices_all(a, b, c, d, answer)  # ← d を渡す
        for dummy in dummies:
            choices.append(f"\\( x = {fmt_for_choice(dummy)} \\)")
        shuffle(choices)
        return latex_answer, latex_problem, choices
    
    def _make_random_number(self, number_type=None, max_num=5, min_num=-5):
        """指定された型のランダムな数を出力する

        Args:
            number_type (Union[str, NoneType], optional): 整数、分数、小数のいずれかの型を指定
            max_num (int, optional): 値決定に使用される数の最大値
            min_num (int, optional): 値決定に使用される数の最小値
        
        Returns:
            number (Union[sy.Integer, sy.Rational]): 計算に使用される数
            number_latex (str): latex形式で記述された数
        
        Raises:
            ValueError: 指定された数の型が存在しない場合発生
        """
        
        def make_random_frac(max_num, min_num):
            """ランダムな分数とlatexを返す

            Args:
                max_num (int): 値決定に使用される数の最大値
                min_num (int): 値決定に使用される数の最小値

            Returns:
                frac (sy.Rational): 計算用の分数
                frac_latex (str): latex形式で記述された表示用の分数
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
            
        
        def make_random_decimal(max_num, min_num):
            """ランダムな小数とlatexを返す

            Args:
                max_num (int): 値決定に使用される数の最大値
                min_num (int): 値決定に使用される数の最小値

            Returns:
                decimal_as_frac (sy.Rational): 計算用の分数
                decimal_latex or integer_latex (str): latex形式で記述された小数
            
            Note:
                小数と分数が混在している時の計算は分数で進める原則と、
                本当にランダムな値を与えると無限小数が出てくることを鑑みて、
                実際の計算は分数で、表示は小数でという設計になっている。
            """
            if random() > 0.5:
                numerator = randint(1, max_num * 10)                    
            else:
                numerator = randint(min_num * 10, -1)
            
            if numerator % 10 == 0:
                if random() > 0.5:
                    numerator += randint(1, 9)
                else:
                    numerator -= randint(1, 9)
            
            decimal_as_frac = sy.Rational(numerator, 10)

            decimal = sy.Float(decimal_as_frac)
            decimal_latex = sy.latex(decimal)
            return decimal_as_frac, decimal_latex
        
        def make_random_integer(max_num, min_num):
            """ランダムな整数とlatexを返す

            Args:
                max_num (int): 値決定に使用される数の最大値
                min_num (int): 値決定に使用される数の最小値

            Returns:
                integer (sy.Integer): 計算用の整数
                integer_latex (str): latex形式で記述された整数
            """
            checker = random()
            if checker > 0.5:
                number = randint(1, max_num)
            else:
                number = randint(min_num, -1)
            
            integer = sy.Integer(number)
            integer_latex = sy.latex(integer)
            return integer, integer_latex
        
        if number_type is not None:
            selected_number_type = number_type
        else:
            selected_number_type = choice(self.numbers_to_use)
            
        if selected_number_type == "integer":
            number, number_latex = make_random_integer(max_num=max_num, min_num=min_num)
        elif selected_number_type == "frac":
            number, number_latex = make_random_frac(max_num=max_num, min_num=min_num)
        elif selected_number_type == "decimal":
            number, number_latex = make_random_decimal(max_num=max_num, min_num=min_num)
        else:
            raise ValueError(f"'selected_number_type' is {selected_number_type}. This may be wrong.")
        
        return number, number_latex
