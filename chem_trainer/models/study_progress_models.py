from django.db import models
from django.utils import timezone
from accounts.models import Student
from django.utils import timezone

from django.apps import apps

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
        """SuperMemo ベースの復習優先度の計算 + Difficulty.level による補正"""

        # ✅ 学習対象の難易度を取得（デフォルト難易度: 1）
        difficulty_level = 1

        ElementDifficulty = apps.get_model('chem_trainer', 'ElementDifficulty')
        SubstanceDifficulty = apps.get_model('chem_trainer', 'SubstanceDifficulty')
        CompoundDifficulty = apps.get_model('chem_trainer', 'CompoundDifficulty')
        EquationDifficulty = apps.get_model('chem_trainer', 'EquationDifficulty')

        try:
            if hasattr(self, 'element') and hasattr(self.element, 'element_difficulty'):
                difficulty_level = self.element.element_difficulty.level
            elif hasattr(self, 'substance') and hasattr(self.substance, 'substance_difficulty'):
                difficulty_level = self.substance.substance_difficulty.level
            elif hasattr(self, 'compound') and hasattr(self.compound, 'compound_difficulty'):
                difficulty_level = self.compound.compound_difficulty.level
            elif hasattr(self, 'chemical_equation') and hasattr(self.chemical_equation, 'equation_difficulty'):
                difficulty_level = self.chemical_equation.equation_difficulty.level
        except ElementDifficulty.DoesNotExist:
            difficulty_level = 1
        except SubstanceDifficulty.DoesNotExist:
            difficulty_level = 1
        except CompoundDifficulty.DoesNotExist:
            difficulty_level = 1
        except EquationDifficulty.DoesNotExist:
            difficulty_level = 1

        # ✅ SuperMemo アルゴリズムの適用
        if is_correct:
            self.ease_factor = max(1.3, self.ease_factor - 0.2 + (0.1 * (5 - (1.0 - self.accuracy_rate) * 5)))
            self.interval = int(self.interval * self.ease_factor)
        else:
            self.interval = 1
            self.ease_factor = max(1.3, self.ease_factor - 0.2)

        # ✅ 難易度を考慮した review_priority の補正
        days_since_last = (timezone.now() - self.last_answered_at).days if self.last_answered_at else 0
        time_factor = (2.718 ** (days_since_last / (self.ease_factor * self.interval)))

        # 難易度が高いほど復習の優先度も上がる
        self.review_priority = (1 / (self.ease_factor * self.interval)) * time_factor * difficulty_level

    @property
    def percent_accuracy(self):
        return round(self.accuracy_rate * 100, 1)  # 小数点1桁で四捨五入

    def get_latex(self):
        """関連するオブジェクトの LaTeX 表記を取得"""
        if hasattr(self, 'substance') and self.substance:
            return self.substance.get_latex()
        elif hasattr(self, 'compound') and self.compound:
            return self.compound.get_latex()
        elif hasattr(self, 'chemical_equation') and self.chemical_equation:
            return self.chemical_equation.get_latex()
        return ""  # 該当なしの場合は空文字

    def get_relation_id(self):
        """関連するオブジェクトの ID を取得"""
        if hasattr(self, 'substance') and self.substance:
            return self.substance.id
        elif hasattr(self, 'compound') and self.compound:
            return self.compound.id
        elif hasattr(self, 'chemical_equation') and self.chemical_equation:
            return self.chemical_equation.id
        return None

    def get_relation_type(self):
        """関連するオブジェクトの種類を取得"""
        if hasattr(self, 'substance') and self.substance:
            return "substance"
        elif hasattr(self, 'compound') and self.compound:
            return "compound"
        elif hasattr(self, 'chemical_equation') and self.chemical_equation:
            return "equation"
        return "unknown"


class StudentElementProgress(BaseProgress):
    """生徒ごとの元素学習進捗"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="element_progress")
    element = models.ForeignKey("Element", on_delete=models.CASCADE, related_name="student_progress")

    def __str__(self):
        return f"{self.student} - {self.element} (優先度: {self.review_priority:.2f})"


class StudentSubstanceProgress(BaseProgress):
    """生徒ごとの単体学習進捗"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="substance_progress")
    substance = models.ForeignKey("ElementalSubstance", on_delete=models.CASCADE, related_name="student_progress")

    def __str__(self):
        return f"{self.student} - {self.substance} (優先度: {self.review_priority:.2f})"


class StudentCompoundProgress(BaseProgress):
    """生徒ごとの化合物学習進捗"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="compound_progress")
    compound = models.ForeignKey("Compound", on_delete=models.CASCADE, related_name="student_progress")

    def __str__(self):
        return f"{self.student} - {self.compound} (優先度: {self.review_priority:.2f})"


class StudentEquationProgress(BaseProgress):
    """生徒ごとの化学反応式学習進捗"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="equation_progress")
    chemical_equation = models.ForeignKey("ChemicalEquation", on_delete=models.CASCADE, related_name="student_progress")

    def __str__(self):
        return f"{self.student} - {self.chemical_equation} (優先度: {self.review_priority:.2f})"

