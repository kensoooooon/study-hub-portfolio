# text_scheduler/forms.py
from django import forms
from text_scheduler.models import LearningMaterial

from django.core.exceptions import ValidationError

from django.utils.translation import gettext_lazy as _

from django.utils import timezone

from text_scheduler.services.feasibility import diagnose_plan



WEEKDAY_CHOICES = [
    (0, "月"), (1, "火"), (2, "水"),
    (3, "木"), (4, "金"), (5, "土"), (6, "日"),
]

class LearningMaterialForm(forms.ModelForm):
    # checkboxの複数選択で受信
    buffer_weekdays = forms.TypedMultipleChoiceField(
        label="予備日(曜日)",
        required=False,
        coerce=int,                       # -> list[int] に自動変換
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        help_text="予備に回したい曜日を選択（未選択可）",
    )

    class Meta:
        model = LearningMaterial
        # 改ざんを避けたいもの（created_by, target_student）は含めない
        fields = [
            "title",
            "unit_label",
            "start_number",
            "end_number",
            "required_reviews",
            "estimated_minutes_per_unit",
            "daily_minutes_budget",
            "start_date",
            "goal_date",
            "buffer_weekdays",
            "is_archived",
        ]
        labels = {
            "title": _("教材名"),
            "unit_label": _("単位ラベル"),
            "start_number": _("開始番号"),
            "end_number": _("終了番号"),
            "required_reviews": _("必要復習回数"),
            "estimated_minutes_per_unit": _("1ユニット想定時間(分)"),
            "daily_minutes_budget": _("この教材に1日あたり費やせる時間(分)"),
            "start_date": _("開始日"),
            "goal_date": _("目標終了日"),
            "buffer_weekdays": _("予備日(曜日)"),
            "is_archived": _("アーカイブ済み"),
        }
        
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "goal_date": forms.DateInput(attrs={"type": "date"}),
            "daily_minutes_budget": forms.NumberInput(attrs={"min":5,"max":600,"step":5}),
        }
        error_messages = {
            "title": {"required": _("教材名は必須です。")},
            "start_date": {"required": _("開始日は必須です。")},
            "goal_date": {"required": _("目標終了日は必須です。")},
        }

        help_texts = {
            "goal_date": _("最終復習が完了しているべき最終日です。必要復習回数に基づいて「初回学習の締切（= 最終復習までのリード日数を差し引いた日）」が自動計算されます。"),
            "required_reviews": _("ここで指定した回数の復習を前提に、初回学習の締切が決まります。"),
        }

    def __init__(self, *args, **kwargs):
        # request はここで取り出してOK
        self.request = kwargs.pop("request", None)
        # ★ 先に親を初期化（fields が生成される）
        super().__init__(*args, **kwargs)

        # 任意：user を使いたい場合
        self.user = getattr(self.request, "user", None) if self.request else None

        # ★ ここで required を立てる
        self.fields["start_date"].required = True
        self.fields["goal_date"].required = True

        # クラスの設定
        for name, field in self.fields.items():
            w = field.widget

            # 1) まず既存の class を必要に応じてクリア（重要）
            if isinstance(w, (forms.CheckboxSelectMultiple,)):
                # コンテナ(div)にも class が乗るので一旦外す
                w.attrs.pop("class", None)

            # 2) チェックボックス/ラジオは form-check-input、それ以外は form-control
            if isinstance(w, (forms.CheckboxInput,)):
                w.attrs.setdefault("class", "form-check-input")
            elif isinstance(w, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
                # ここではコンテナに class を付けない（個々の input に class を付けたい場合は renderer をカスタムする）
                pass
            else:
                w.attrs.setdefault("class", "form-control")

            # DateInput の保険（必要なら）
            if isinstance(w, forms.DateInput):
                w.attrs.setdefault("type", "date")

    def clean_buffer_weekdays(self):
        data = self.cleaned_data.get("buffer_weekdays") or []
        # TypedMultipleChoiceField(coerce=int) なので通常は int だが、念のため検証
        try:
            data = [int(x) for x in data]
        except (TypeError, ValueError):
            raise ValidationError(_("予備日(曜日)は整数で指定してください。"))
        if any(v < 0 or v > 6 for v in data):
            raise ValidationError(_("曜日は 0(月)〜6(日) の範囲で指定してください。"))
        # 重複排除＋安定化
        return sorted(set(data))


    def clean(self):
        cleaned = super().clean()
        s = cleaned.get("start_number")
        e = cleaned.get("end_number")
        if s is not None and e is not None and e < s:
            self.add_error("end_number", _("終了番号は開始番号以上にしてください。"))

        sd = cleaned.get("start_date")
        gd = cleaned.get("goal_date")
        if sd and gd and gd < sd:
            self.add_error("goal_date", _("目標終了日は開始日以降にしてください。"))

        # 例: 今日より過去開始を禁止したい場合（不要なら削除）
        if sd and sd < timezone.localdate():
            self.add_error("start_date", _("開始日は本日以降を指定してください。"))
        # --- ここから「最終復習までを考慮した妥当性チェック」 ---
        unit   = cleaned.get("estimated_minutes_per_unit")
        budget = cleaned.get("daily_minutes_budget")
        req    = cleaned.get("required_reviews")
        buffers = cleaned.get("buffer_weekdays") or []
        u1 = cleaned.get("start_number")
        u2 = cleaned.get("end_number")

        # 必須が揃ったときのみ診断（None ガード）
        if all(v is not None for v in [sd, gd, u1, u2, unit, budget, req]):
            diag = diagnose_plan(
                sd, gd, u1, u2, unit, budget,
                required_reviews=req,
                buffer_weekdays=buffers,
            )
            # ビューでの messages 用に保持（任意）
            self._diagnosis = diag

            if diag.get("status") == "impossible":
                fd = diag.get("first_deadline") or "（算出不可）"
                raise ValidationError(
                    _("最終復習が目標日までに終わりません。初回学習の締切: %(fd)s / "
                    "必要新規/日: %(need)s / 上限/日: %(cap)s"),
                    params={"fd": fd, "need": diag.get("req_new_per_day"), "cap": diag.get("cap_new_per_day")},
                )
        return cleaned
