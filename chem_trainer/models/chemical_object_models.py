from django.db import models
from django.core.exceptions import ValidationError

import re
import math
import random


# 元素情報を管理するモデル
class Element(models.Model):
    symbol = models.CharField(max_length=5, unique=True)  # 元素記号 (例: Na, O, C)
    name_jp = models.CharField(max_length=100)  # 日本語名 (例: ナトリウム)
    name_en = models.CharField(max_length=100)  # 英語名 (例: Sodium)
    atomic_number = models.PositiveIntegerField(unique=True)  # 原子番号 (例: 11)
    category = models.CharField(max_length=50, choices=[
        ('alkali_metal', 'アルカリ金属'),
        ('alkaline_earth_metal', 'アルカリ土類金属'),
        ('halogen', 'ハロゲン'),
        ('noble_gas', '貴ガス'),
        ('other_metal', 'その他の金属元素'),
        ('other_nonmetal', 'その他の非金属元素'),
        ('transition_metal', '遷移元素'),
    ])
    latex = models.CharField(max_length=100, blank=True, null=True)  # LaTeX 表示用

    def __str__(self):
        return f"{self.symbol} ({self.name_jp})"

    def get_latex(self):
        """LaTeX 用の表示を取得"""
        return f"\( {self.latex or self.symbol} \)"


# 単体 (Elemental Substance) を管理するモデル
class ElementalSubstance(models.Model):
    formula = models.CharField(max_length=50, unique=True)  # 化学式 (例: O2, N2, H2)
    name_jp = models.CharField(max_length=100)  # 日本語名 (例: 酸素, 窒素, 水素)
    name_en = models.CharField(max_length=100)  # 英語名 (例: Oxygen, Nitrogen, Hydrogen)
    element = models.ForeignKey(Element, on_delete=models.CASCADE, related_name='substances')  # 元素との関連
    latex = models.CharField(max_length=100, blank=True, null=True)  # LaTeX 表示用

    def clean(self):
        """単体の元素が `Element` に登録されているかチェック"""
        if not Element.objects.filter(symbol=self.element.symbol).exists():
            raise ValidationError(f"単体 '{self.formula}' の元素 '{self.element.symbol}' が Element に登録されていません。")

    def save(self, *args, **kwargs):
        self.clean()  # データ整合性チェック
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.formula} ({self.name_jp})"

    def get_clean_latex(self):
        """LaTeX の出力を整理"""
        return self.latex or self.equation

    def get_latex(self):
        return f"\( {self.get_clean_latex()} \)"


# 化合物(Compound)を管理するモデル
class Compound(models.Model):
    formula = models.CharField(max_length=50, unique=True)  # 化学式 (例: CO2, NaCl)
    name_jp = models.CharField(max_length=100)  # 日本語名 (例: 二酸化炭素)
    name_en = models.CharField(max_length=100)  # 英語名 (例: Carbon Dioxide)
    elements = models.ManyToManyField(Element, related_name='compounds', blank=True)  # 含まれる元素
    latex = models.CharField(max_length=100, blank=True, null=True)  # LaTeX 表示用

    def validate_elements(self):
        """化合物の元素が `Element` に登録されているかチェック"""
        missing_elements = [e.symbol for e in self.elements.all() if not Element.objects.filter(symbol=e.symbol).exists()]
        if missing_elements:
            raise ValidationError(f"化合物 '{self.formula}' に含まれる元素が `Element` に登録されていません: {', '.join(missing_elements)}。")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)  # まず `save()` して ID を確定
        self.validate_elements()  # `elements` 登録後にバリデーションを実行

    def __str__(self):
        return f"{self.formula} ({self.name_jp})"

    def get_clean_latex(self):
        """LaTeX の出力を整理"""
        return self.latex or self.equation

    def get_latex(self):
        return f"\( {self.get_clean_latex()} \)"


class ChemicalEquation(models.Model):
    equation = models.CharField(max_length=255, unique=True)  # 反応式 (例: C + O2 = CO2)
    reactant_substances = models.ManyToManyField('ElementalSubstance', related_name='reactant_in', blank=True)  # 反応物（単体）
    reactant_compounds = models.ManyToManyField('Compound', related_name='reactant_compound_in', blank=True)  # 反応物（化合物）
    product_substances = models.ManyToManyField('ElementalSubstance', related_name='product_in', blank=True)  # 生成物（単体）
    product_compounds = models.ManyToManyField('Compound', related_name='product_compound_in', blank=True)  # 生成物（化合物）
    latex = models.CharField(max_length=255, blank=True, null=True)  # LaTeX 表示用

    def validate_chemicals(self):
        """反応式の成分が `ElementalSubstance` または `Compound` に登録されているかチェック"""
        all_reactants = set(self.reactant_substances.values_list('formula', flat=True)) | set(self.reactant_compounds.values_list('formula', flat=True))
        all_products = set(self.product_substances.values_list('formula', flat=True)) | set(self.product_compounds.values_list('formula', flat=True))

        missing_reactants = [formula for formula in all_reactants if not (ElementalSubstance.objects.filter(formula=formula).exists() or Compound.objects.filter(formula=formula).exists())]
        missing_products = [formula for formula in all_products if not (ElementalSubstance.objects.filter(formula=formula).exists() or Compound.objects.filter(formula=formula).exists())]

        if missing_reactants or missing_products:
            raise ValidationError(f"以下の物質が未登録です: {', '.join(missing_reactants + missing_products)}。登録してください。")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.validate_chemicals()

    def __str__(self):
        return f"{self.equation}"

    def get_clean_latex(self):
        """LaTeX の出力を整理"""
        return self.latex or self.equation
    
    def get_latex(self):
        """\(\)付きのLaTeXを取得"""
        return f"\( {self.get_clean_latex()} \)"

    def get_latex_without_coefficients(self):
        """係数なしの化学反応式を生成（{} 内の数字は保持し、先頭の係数のみ削除）"""
        clean_latex = self.get_latex()
        return re.sub(r'(\b\d+)([A-Za-z])', r'\2', clean_latex)

    def get_coefficients(self):
        """ChemicalEquation の LaTeX から係数リストを取得"""
        latex_equation = self.get_clean_latex()
        # 反応物・生成物を取得
        reactants = list(self.reactant_substances.all()) + list(self.reactant_compounds.all())
        products = list(self.product_substances.all()) + list(self.product_compounds.all())
        # 全化学式をリスト化（LaTeX 表記）
        chemical_formulas = [s.get_clean_latex() for s in reactants + products]

        coefficients = []
        formulas = []
        # 各化学式について、LaTeX から係数を取得
        for formula in chemical_formulas:
            pattern = rf"(\d+)?\s*{re.escape(formula)}"
            match = re.search(pattern, latex_equation)
            if match:
                coeff = int(match.group(1)) if match.group(1) else 1  # 係数がない場合は 1
                coefficients.append(coeff)
                formulas.append(formula)
        return coefficients, formulas

    def generate_wrong_answers_for_fill_coefficients(self, num_choices=3):
        """ 係数のランダムな変更を伴う誤答を生成 """
        correct_coeffs, formulas = self.get_coefficients()
        wrong_answers = set()
        
        latex_template = self.get_latex_without_coefficients()  # 順番を保持したままのテンプレート

        while len(wrong_answers) < num_choices:
            modified_coeffs = correct_coeffs[:]

            # ✅ 変更する箇所をランダムに決定 (最低1箇所)
            num_changes = random.randint(1, len(correct_coeffs))
            change_indices = random.sample(range(len(correct_coeffs)), num_changes)

            # ✅ 係数の変更
            for idx in change_indices:
                modified_coeffs[idx] = random.randint(1, 5)  # 1~5の範囲で新しい係数を設定

            # ✅ 最大公約数が 1 以上の場合、修正処理を追加
            while math.gcd(*modified_coeffs) > 1:
                if all(c == 1 for c in modified_coeffs):
                    break
                if all(c > 1 for c in modified_coeffs):
                    idx = random.choice(range(len(correct_coeffs)))
                    modified_coeffs[idx] = 1  # ランダムな1を含めるように変更

            # ✅ 変更後の式を生成（元の順番を保持）
            modified_equation = latex_template
            for coeff, formula in zip(modified_coeffs, formulas):
                pattern = rf"\b{re.escape(formula)}\b"
                replacement = f"{coeff}{formula}" if coeff > 1 else formula
                modified_equation = re.sub(pattern, replacement, modified_equation)

            # ✅ 正解と重複しないことを確認
            if modified_equation != self.get_clean_latex():
                wrong_answers.add(modified_equation)

        return list(wrong_answers)

    def generate_wrong_answers_for_complete_equation(self, hide_part, num_choices=3):
        """ `complete_equation` 用の誤答を生成（関連する物質を基にする） """
        
        # 正解の反応物・生成物を取得
        reactants = [s.get_latex() for s in self.reactant_substances.all()] + [c.get_latex() for c in self.reactant_compounds.all()]
        products = [s.get_latex() for s in self.product_substances.all()] + [c.get_latex() for c in self.product_compounds.all()]

        if hide_part == 'reactants':
            correct_answer = ' + '.join(reactants)
            correct_elements = {e.symbol for c in self.reactant_compounds.all() for e in c.elements.all()}
        else:
            correct_answer = ' + '.join(products)
            correct_elements = {e.symbol for c in self.product_compounds.all() for e in c.elements.all()}

        # 関連する単体・化合物を取得
        related_substances = ElementalSubstance.objects.filter(element__symbol__in=correct_elements)
        related_compounds = Compound.objects.filter(elements__symbol__in=correct_elements)

        # ダミー選択肢を生成
        wrong_answers = set()
        
        while len(wrong_answers) < num_choices:
            # 関連する物質を優先
            if random.random() < 0.7 and related_compounds.exists():
                choice = random.choice(related_compounds).get_latex()
            elif related_substances.exists():
                choice = random.choice(related_substances).get_latex()
            else:
                # 関連物質が足りなければ、完全ランダム
                choice = random.choice(Compound.objects.exclude(id=self.id)).get_latex()

            if choice != correct_answer:
                wrong_answers.add(choice)

        return list(wrong_answers)

