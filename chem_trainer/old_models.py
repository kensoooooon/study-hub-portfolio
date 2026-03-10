from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from accounts.models import Student  # 生徒情報の紐付け
from django.utils import timezone


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
        return f"${self.latex or self.symbol}$"


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

    def get_latex(self):
        return f"${self.latex or self.formula}$"


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

    def get_latex(self):
        return f"${self.latex or self.formula}$"


# 化学反応式を管理するモデル（データ整合性チェック含む）
class ChemicalEquation(models.Model):
    equation = models.CharField(max_length=255, unique=True)  # 反応式 (例: C + O2 = CO2)
    reactant_substances = models.ManyToManyField(ElementalSubstance, related_name='reactant_in', blank=True)  # 反応物（単体）
    reactant_compounds = models.ManyToManyField(Compound, related_name='reactant_compound_in', blank=True)  # 反応物（化合物）
    product_substances = models.ManyToManyField(ElementalSubstance, related_name='product_in', blank=True)  # 生成物（単体）
    product_compounds = models.ManyToManyField(Compound, related_name='product_compound_in', blank=True)  # 生成物（化合物）
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
        super().save(*args, **kwargs)  # まず `save()` して ID を確定
        self.validate_chemicals()  # `reactants`・`products` 登録後にバリデーションを実行

    def __str__(self):
        return f"{self.equation}"

    def get_latex(self):
        return f"${self.latex or self.equation}$"


# 難易度を管理するモデル
class Difficulty(models.Model):
    level = models.PositiveSmallIntegerField(default=1)  # 難易度レベル
    description = models.CharField(max_length=255, blank=True, null=True)
    chemical_equation = models.OneToOneField(ChemicalEquation, on_delete=models.CASCADE, related_name='difficulty')

    def __str__(self):
        return f"{self.chemical_equation} - Level {self.level}"


# 生徒ごとの学習進捗を管理するモデル
class BaseProgress(models.Model):
    """学習進捗の共通基底モデル"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="progress")
    correct_count = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)
    accuracy_rate = models.FloatField(default=0.0)
    last_answered_at = models.DateTimeField(null=True, blank=True)
    review_priority = models.FloatField(default=1.0)
    ease_factor = models.FloatField(default=2.5)
    interval = models.PositiveIntegerField(default=1)

    class Meta:
        abstract = True  # これを設定すると、このモデル単体でDBにテーブルが作成されない

    def update_progress(self, is_correct):
        """正答率と復習優先度を更新"""
        self.total_count += 1
        if is_correct:
            self.correct_count += 1
        self.accuracy_rate = self.correct_count / self.total_count if self.total_count > 0 else 0.0
        self.last_answered_at = timezone.now()
        self.update_review_priority(is_correct)
        self.save()

    def update_review_priority(self, is_correct):
        """SuperMemo ベースの復習優先度の計算"""
        if is_correct:
            self.ease_factor = max(1.3, self.ease_factor - 0.2 + (0.1 * (5 - (1.0 - self.accuracy_rate) * 5)))
            self.interval = int(self.interval * self.ease_factor)
        else:
            self.interval = 1
            self.ease_factor = max(1.3, self.ease_factor - 0.2)

        days_since_last = (timezone.now() - self.last_answered_at).days if self.last_answered_at else 0
        time_factor = (2.718 ** (days_since_last / (self.ease_factor * self.interval)))
        self.review_priority = (1 / (self.ease_factor * self.interval)) * time_factor


class StudentElementProgress(BaseProgress):
    """生徒ごとの元素学習進捗"""
    element = models.ForeignKey("Element", on_delete=models.CASCADE, related_name="student_progress")

    def __str__(self):
        return f"{self.student} - {self.element} (優先度: {self.review_priority:.2f})"


class StudentSubstanceProgress(BaseProgress):
    """生徒ごとの単体学習進捗"""
    substance = models.ForeignKey("ElementalSubstance", on_delete=models.CASCADE, related_name="student_progress")

    def __str__(self):
        return f"{self.student} - {self.substance} (優先度: {self.review_priority:.2f})"


class StudentCompoundProgress(BaseProgress):
    """生徒ごとの化合物学習進捗"""
    compound = models.ForeignKey("Compound", on_delete=models.CASCADE, related_name="student_progress")

    def __str__(self):
        return f"{self.student} - {self.compound} (優先度: {self.review_priority:.2f})"


class StudentEquationProgress(BaseProgress):
    """生徒ごとの化学反応式学習進捗"""
    chemical_equation = models.ForeignKey("ChemicalEquation", on_delete=models.CASCADE, related_name="student_progress")

    def __str__(self):
        return f"{self.student} - {self.chemical_equation} (優先度: {self.review_priority:.2f})"
