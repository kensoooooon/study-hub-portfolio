from django import forms
from text_scheduler.models import StudyLog
from django.forms import formset_factory


class StudyLogForm(forms.ModelForm):
    class Meta:
        model = StudyLog
        fields = ["number", "kind", "quality", "spent_minutes",
                "point_1", "point_2", "point_3", "is_correct"]
        # ※ kind の widget は下のフィールド定義で付けるので、ここでは指定しません

    # モデル側の単一ソースを参照（フォーム内で別定義しない）
    kind = forms.ChoiceField(choices=StudyLog.KIND_CHOICES)
    # 未選択/不明を許容
    IS_CORRECT_CHOICES = [("true", "正解"), ("false", "不正解"), ("unknown", "不明")]
    is_correct = forms.ChoiceField(choices=IS_CORRECT_CHOICES, required=False)

    def __init__(self, *args, **kwargs):
        student = kwargs.pop("student", None)
        material = kwargs.pop("material", None)
        super().__init__(*args, **kwargs)
        # ここで instance に差し込む（clean() 前に material/student がある状態にする）
        inst = self.instance
        if student is not None:
            inst.student = student
        if material is not None:
            inst.material = material

        # ▼ ここを追加：HTML5バリデーションのヒント
        if inst.material:
            mn, mx = inst.material.start_number, inst.material.end_number
            self.fields["number"].widget.attrs.update({
                "type": "number",
                "min": mn, "max": mx,
                "inputmode": "numeric",
                "placeholder": f"{inst.material.unit_label}{mn}〜{mx}",
            })
            self.fields["number"].help_text = f"{inst.material.unit_label}{mn}〜{mx} の範囲で入力してください"

    def clean_number(self):
        n = self.cleaned_data.get("number")
        if n is None:
            raise forms.ValidationError("番号は必須です。")
        m = self.instance.material
        if m and not (m.start_number is None or m.end_number is None):
            if not (m.start_number <= n <= m.end_number):
                raise forms.ValidationError(f"番号が教材の範囲外です（{m.start_number}〜{m.end_number}）。")
        return n

StudyLogFormSet = formset_factory(
    StudyLogForm,
    extra=1,
    can_delete=True,
    max_num=20,
    validate_max=True,
)
