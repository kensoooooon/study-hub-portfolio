from django.db import models
from chem_trainer.models import Element, ElementalSubstance, Compound, ChemicalEquation


class BaseDifficulty(models.Model):
    """難易度の共通基底モデル"""
    level = models.PositiveSmallIntegerField(default=1)
    description = models.CharField(max_length=255, blank=True, null=True)
    correct_count = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True

    def update_difficulty(self, is_correct):
        """正解数・総解答数をもとに難易度を更新"""
        self.total_count += 1
        if is_correct:
            self.correct_count += 1

        accuracy_rate = self.correct_count / self.total_count if self.total_count > 0 else 0.0

        # ✅ 難易度の更新ロジック（低正解率ならレベルUP）
        if accuracy_rate < 0.3:
            self.level = min(self.level + 1, 5)  # 最大レベル5
        elif accuracy_rate > 0.7:
            self.level = max(self.level - 1, 1)  # 最小レベル1

        self.save()

class ElementDifficulty(BaseDifficulty):
    element = models.OneToOneField(Element, on_delete=models.CASCADE, related_name='element_difficulty')

class SubstanceDifficulty(BaseDifficulty):
    substance = models.OneToOneField(ElementalSubstance, on_delete=models.CASCADE, related_name='substance_difficulty')

class CompoundDifficulty(BaseDifficulty):
    compound = models.OneToOneField(Compound, on_delete=models.CASCADE, related_name='compound_difficulty')

class EquationDifficulty(BaseDifficulty):
    chemical_equation = models.OneToOneField(ChemicalEquation, on_delete=models.CASCADE, related_name='equation_difficulty')
