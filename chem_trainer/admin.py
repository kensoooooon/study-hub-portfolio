from django.contrib import admin
from django.core.exceptions import ValidationError
from chem_trainer.models import Element, ElementalSubstance, Compound, ChemicalEquation
from chem_trainer.models import StudentElementProgress, StudentSubstanceProgress, StudentCompoundProgress, StudentEquationProgress
from chem_trainer.models import ElementDifficulty, SubstanceDifficulty, CompoundDifficulty, EquationDifficulty

class BaseProgressAdmin(admin.ModelAdmin):
    """ 学習進捗の共通管理画面 """
    list_display = ('student', 'get_target', 'correct_count', 'total_count', 'accuracy_rate', 'review_priority')
    list_filter = ('student',)
    search_fields = ('student__username',)

    def get_target(self, obj):
        """ 進捗対象（元素・単体・化合物・化学反応式）を取得 """
        return obj.element or obj.substance or obj.compound or obj.chemical_equation
    get_target.short_description = "学習対象"

    def save_model(self, request, obj, form, change):
        try:
            obj.full_clean()  # バリデーションを実行
            super().save_model(request, obj, form, change)
        except ValidationError as e:
            self.message_user(request, f"エラー: {e}", level='error')

class BaseDifficultyAdmin(admin.ModelAdmin):
    """ 難易度管理の共通管理画面 """
    list_display = ('get_target', 'level', 'correct_count', 'total_count')
    list_filter = ('level',)
    search_fields = ('get_target',)

    def get_target(self, obj):
        """ 難易度対象（元素・単体・化合物・化学反応式）を取得 """
        return obj.element or obj.substance or obj.compound or obj.chemical_equation
    get_target.short_description = "対象"

# 各学習進捗を共通管理クラスで登録
admin.site.register(StudentElementProgress, BaseProgressAdmin)
admin.site.register(StudentSubstanceProgress, BaseProgressAdmin)
admin.site.register(StudentCompoundProgress, BaseProgressAdmin)
admin.site.register(StudentEquationProgress, BaseProgressAdmin)

# 難易度管理
admin.site.register(ElementDifficulty, BaseDifficultyAdmin)
admin.site.register(SubstanceDifficulty, BaseDifficultyAdmin)
admin.site.register(CompoundDifficulty, BaseDifficultyAdmin)
admin.site.register(EquationDifficulty, BaseDifficultyAdmin)

# その他のモデルを登録
admin.site.register(Element)
admin.site.register(ElementalSubstance)
admin.site.register(Compound)
admin.site.register(ChemicalEquation)
