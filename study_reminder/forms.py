from django import forms
from .models import StudyReminder
from study_reminder.services.learning_link_availability import check_learning_link_availability


class StudyReminderBaseForm(forms.ModelForm):
    """
    StudyReminder作成・編集フォームの共通基底クラス
    """
    class Meta:
        model = StudyReminder
        fields = ['day_of_week', 'time_of_day', 'custom_message', 'learning_link_destination']
        labels = {
            'day_of_week': '曜日',
            'time_of_day': '時間',
            'custom_message': 'カスタムメッセージ',
            'learning_link_destination': '学習リンク',
        }
        widgets = {
            'day_of_week': forms.Select(attrs={'class': 'form-select'}),
            'custom_message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': '通知メッセージを入力（改行可能）'
            }),
            'learning_link_destination': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 時刻フィールドを15分単位の選択肢に変更
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

    def _apply_availability_guard(self):
        """各 destination を個別に check_learning_link_availability() に通し、
        allowed=True のものだけ choices に残す。NONE ("") は常に残す。
        """
        student = getattr(self, "student", None)
        if not student:
            return

        field = self.fields["learning_link_destination"]
        available_choices = []
        for value, label in field.choices:
            if value == "":
                available_choices.append((value, label))
                continue
            if check_learning_link_availability(student, value).allowed:
                available_choices.append((value, label))

        field.choices = available_choices

        if len(available_choices) == 1:
            if not student.email:
                field.help_text = (
                    "この生徒にはメールアドレスが登録されていないため、ログイン誘導リンクは追加できません。"
                )
            else:
                field.help_text = (
                    "この生徒には現在設定可能な学習リンクがありません。"
                )

    def clean(self):
        cleaned_data = super().clean()
        destination = cleaned_data.get("learning_link_destination", "")
        student = getattr(self, "student", None)
        if destination and student:
            availability = check_learning_link_availability(student, destination)
            if not availability.allowed:
                self.add_error(
                    "learning_link_destination",
                    "この生徒にはこの学習リンクを設定できません。",
                )
        return cleaned_data


class StudyReminderCreateForm(StudyReminderBaseForm):
    """
    StudyReminder作成専用フォーム
    """
    def __init__(self, *args, **kwargs):
        self.student = kwargs.pop("student", None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.user = user
        self._apply_availability_guard()


class StudyReminderEditForm(StudyReminderBaseForm):
    """
    StudyReminder編集専用フォーム
    """
    def __init__(self, *args, **kwargs):
        self.student = kwargs.pop("student", None)
        super().__init__(*args, **kwargs)

        # 既存データをデフォルト表示
        if self.instance:
            self.fields['day_of_week'].initial = self.instance.day_of_week
            self.fields['time_of_day'].initial = self.instance.time_of_day.strftime('%H:%M')
            self.fields['custom_message'].initial = self.instance.custom_message

        self._apply_availability_guard()

    def clean_custom_message(self):
        value = self.cleaned_data.get('custom_message')
        return value or None
