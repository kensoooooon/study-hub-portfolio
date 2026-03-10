from django import forms
from .models import StudyReminder
from accounts.models import Student


class StudyReminderBaseForm(forms.ModelForm):
    """
    StudyReminder作成・編集フォームの共通基底クラス
    """
    class Meta:
        model = StudyReminder
        fields = ['day_of_week', 'time_of_day', 'custom_message']
        labels = {
            'day_of_week': '曜日',
            'time_of_day': '時間',
            'custom_message': 'カスタムメッセージ',
        }
        widgets = {
            'day_of_week': forms.Select(attrs={'class': 'form-select'}),
            # custom_message を Textarea に変更して改行可能にする
            'custom_message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': '通知メッセージを入力（改行可能）'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 時刻フィールドを30分単位の選択肢に変更
        self.fields['time_of_day'].widget = forms.Select(
            attrs={'class': 'form-select'},
            choices=self.generate_time_choices()
        )

    @staticmethod
    def generate_time_choices():
        """
        15分単位の時刻選択肢を生成
        """
        time_choices = []
        for hour in range(24):  # 0時から23時まで
            for minute in (0, 15, 30, 45):  # 15分単位
                time_label = f"{hour:02}:{minute:02}"
                time_choices.append((time_label, time_label))
        return time_choices


class StudyReminderCreateForm(StudyReminderBaseForm):
    """
    StudyReminder作成専用フォーム
    """
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # 必要に応じてユーザー情報を受け取る
        super().__init__(*args, **kwargs)
        self.user = user


class StudyReminderEditForm(StudyReminderBaseForm):
    """
    StudyReminder編集専用フォーム
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 既存データをデフォルト表示
        if self.instance:
            self.fields['day_of_week'].initial = self.instance.day_of_week
            self.fields['time_of_day'].initial = self.instance.time_of_day.strftime('%H:%M')
            self.fields['custom_message'].initial = self.instance.custom_message or "ChatGPTの自動メッセージ"
