from django import forms
from django.conf import settings
from django.db.models import Q
from django.core.exceptions import ValidationError

from accounts.models import BaseUser,Student, Teacher, OrganizationAdministrator, ClassroomAdministrator
from accounts.models import Classroom, Organization
from vocab_trainer.models import Textbook
from accounts.selectors import visible_students_qs


class ClassroomCreateForm(forms.ModelForm):
    class Meta:
        model = Classroom
        fields = ['name', 'description']
        labels = {
            'name': '教室名',
            'description': '説明',
        }

    def clean_name(self):
        """
        教室名が既に登録されていないかチェックする
        """
        name = self.cleaned_data.get('name')
        if Classroom.objects.filter(name=name).exists():
            raise forms.ValidationError("この教室名はすでに登録されています。")
        return name


class ClassroomEditForm(forms.ModelForm):
    administrators = forms.ModelMultipleChoiceField(
        queryset=ClassroomAdministrator.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="教室管理者"
    )

    class Meta:
        model = Classroom
        fields = ['name', 'description', 'administrators']
        labels = {
            'name': '教室名',
            'description': '説明',
            'administrators': '管理者',
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)

        # 組織管理者のみが教室管理者を設定可能
        if self.current_user and self.current_user.role == 'organization_administrator':
            admin = self.current_user.get_role_object()
            if admin:
                self.fields["administrators"].queryset = (
                    ClassroomAdministrator.objects.filter(
                        organization_id=admin.organization_id,
                    )
                )
        else:
            del self.fields['administrators']  # 教室管理者には表示しない


class AssignClassroomForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.none())
    classroom = forms.ModelChoiceField(queryset=Classroom.objects.none())

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop("current_user", None)
        super().__init__(*args, **kwargs)

        if not self.current_user or self.current_user.role != "organization_administrator":
            return

        org_admin = self.current_user.get_role_object()
        if not org_admin:
            return

        self.fields["student"].queryset = visible_students_qs(self.current_user).filter(
            classrooms__isnull=True,
            line_user_id__isnull=False,
        )

        self.fields["classroom"].queryset = org_admin.get_accessible_classrooms()

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get("student")
        classroom = cleaned_data.get("classroom")

        if not student or not classroom or not self.current_user:
            return cleaned_data

        if not visible_students_qs(self.current_user).filter(pk=student.pk).exists():
            raise forms.ValidationError("操作できない生徒が選択されています。")

        org_admin = self.current_user.get_role_object()
        if not org_admin or not org_admin.get_accessible_classrooms().filter(pk=classroom.pk).exists():
            raise forms.ValidationError("管理下にない教室が選択されています。")

        if student.organization_id != classroom.organization_id:
            raise forms.ValidationError(
                "生徒の所属組織と教室の所属組織が一致していません。"
            )

        return cleaned_data

    def save(self):
        student: Student = self.cleaned_data["student"]
        classroom: Classroom = self.cleaned_data["classroom"]

        student.classrooms.add(classroom)
        return student


class StudentEditForm(forms.ModelForm):
    textbook = forms.ModelChoiceField(
        queryset=Textbook.objects.active(),
        required=False,
        label="使用教科書"
    )
    reset_password = forms.BooleanField(
        required=False,
        label="デフォルトパスワードにリセット"
    )

    class Meta:
        model = Student
        fields = ['username', 'grade', 'teachers', 'email', 'textbook']
        widgets = {
            'teachers': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        """
        ログインユーザーと生徒の所属組織に応じて、
        担当講師の候補を絞り込む
        """
        self.current_user = kwargs.pop("current_user", None)
        self.student = kwargs.pop("student", None)
        super().__init__(*args, **kwargs)

        # 初期値は何も見えないようにしておく（多重防衛）
        qs = Teacher.objects.none()

        if self.current_user:
            role = self.current_user.role
            role_obj = self.current_user.get_role_object()

            if role == "organization_administrator" and isinstance(role_obj, OrganizationAdministrator):
                # 管理している組織に属する講師のみ
                qs = Teacher.objects.filter(organization_id=role_obj.organization_id)

            elif role == "classroom_administrator" and isinstance(role_obj, ClassroomAdministrator):
                # 管理している教室に所属している講師のみ
                qs = Teacher.objects.filter(
                    classrooms__in=role_obj.classrooms.all()
                )

        # さらに「生徒の所属組織」に絞る（二重チェック）
        if self.student:
            qs = qs.filter(organization=self.student.organization)

        self.fields["teachers"].queryset = qs.distinct()

        # 基本はアクティブなもののみだが、既に選択しているテキストが存在する場合は、それも引き続き選択できるように
        textbook_qs = Textbook.objects.active()
        current_textbook_id = (
            (self.instance.textbook_id if self.instance else None)
            or (self.student.textbook_id if self.student else None)
        )
        if current_textbook_id:
            textbook_qs = Textbook.objects.filter(
                Q(is_active=True) | Q(pk=current_textbook_id)
            )
        self.fields["textbook"].queryset = textbook_qs


class TeacherEditForm(forms.ModelForm):
    reset_password = forms.BooleanField(
        required=False,
        label="デフォルトパスワードにリセット",
    )

    class Meta:
        model = Teacher
        fields = ['username', 'email', 'classrooms']
        labels = {
            'username': '氏名',
            'email': 'メールアドレス',
            'classrooms': '所属教室',
        }
        widgets = {
            'classrooms': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        classrooms_queryset = kwargs.pop('classrooms_queryset', Classroom.objects.none())
        super().__init__(*args, **kwargs)

        # アクセス可能な教室のみ選択肢にする
        self.fields['classrooms'].queryset = classrooms_queryset

    def save(self, commit=True):
        teacher = super().save(commit=False)
        classrooms = self.cleaned_data.get("classrooms")  # 選択された教室

        if self.cleaned_data.get("reset_password"):
            teacher.set_default_password()

        if commit:
            teacher.save()
            teacher.classrooms.set(classrooms)  # ⭐ 教室の変更を適用
        return teacher


class TeacherCreateForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"placeholder": "パスワードを入力"}),
        label="パスワード",
        help_text="空白の場合、デフォルトのパスワードが設定されます"
    )

    class Meta:
        model = Teacher
        fields = ['username', 'email', 'classrooms']

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        classrooms_queryset = kwargs.pop('classrooms_queryset', Classroom.objects.none())
        super().__init__(*args, **kwargs)

        # アクセス可能な教室のみを選択肢にする
        self.fields['classrooms'].queryset = classrooms_queryset


    def save(self, commit=True):
        teacher = super().save(commit=False)  # 一旦DBに保存せず、必要な情報を後から追加していく
        password = self.cleaned_data.get("password")
        classrooms = self.cleaned_data.get("classrooms")

        if password:
            teacher.set_password(password)
        else:
            teacher.set_password(settings.TEACHER_DEFAULT_PASSWORD)  # SET_DEFAULT_PASSWORDだとsaveが走る
            teacher.is_first_login = True

        if commit: # 引数で与えられているものを取る。super側ではない点に注意
            teacher.save()
            teacher.classrooms.set(classrooms)  # 教室を適切に紐付ける
        return teacher

    def clean(self):
        cleaned_data = super().clean()
        self.instance.role = 'teacher'  # 新規作成時にroleを補完

        classrooms = cleaned_data.get('classrooms')
        if classrooms:
            organization_ids = set(classrooms.values_list('organization_id', flat=True))  # ToDo: 同一の組織管理者が異なる組織を持っている場合は後発のissueでルールを決めること
            if len(organization_ids) > 1:
                raise ValidationError(
                    {'classrooms': '選択した教室が複数の組織にまたがっています。同一組織内の教室を選択してください。'}
                )
            self.instance.organization_id = organization_ids.pop()

        return cleaned_data

    def _post_clean(self):
        # 教室が1つも確定しなかった場合（未選択 / 選択教室が全て権限外）、
        # organization_idが未確定のままTeacher.clean()が呼ばれ、
        # Teacher.organization.RelatedObjectDoesNotExistで500になるのを防ぐ。
        # モデル側のorganization_idガード化は別途対応する。
        try:
            super()._post_clean()
        except Teacher.organization.RelatedObjectDoesNotExist:
            self.add_error(
                'classrooms',
                '所属組織を確定できませんでした。教室を選択してください。'
            )

    def clean_classrooms(self):
        classrooms = self.cleaned_data.get('classrooms')
        user = self.current_user

        # 何も選択されていない場合はここで返す
        if not classrooms:
            return classrooms

        valid_classrooms = Classroom.objects.filter(id__in=[
            c.id for c in Classroom.objects.all() if c.can_be_accessed_by(user)
        ])

        invalid_classrooms = [c for c in classrooms if c not in valid_classrooms]
        if invalid_classrooms:
            raise ValidationError(
                f"以下の教室にアクセスする権限がありません: {[str(c) for c in invalid_classrooms]}"
            )

        return classrooms


class AccountEditForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"placeholder": "新しいパスワードを入力"}),
        label="新しいパスワード",
        help_text="空白の場合は変更されません（初回ログイン時は必須）",
    )
    password_confirm = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"placeholder": "パスワードを再入力"}),
        label="パスワード（確認）",
    )

    class Meta:
        model = BaseUser
        fields = ['email', 'password']
        labels = {
            'email': 'メールアドレス'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.is_first_login:  # 初回パスワード変更時はメールアドレス変更させない(セキュリティ)
            self.fields['email'].disabled = True

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")

        if password:  # 空でない場合のみセット
            user.set_password(password)
            user.is_first_login = False
        else:
            # 再取得して現在のハッシュ値を維持
            current_password = BaseUser.objects.get(pk=user.pk).password
            user.password = current_password
        if commit:
            user.save()
        return user

    def _get_role_default_password(self, role: str) -> str | None:
        if role == "student":
            return getattr(settings, "STUDENT_DEFAULT_PASSWORD", None)
        if role == "teacher":
            return getattr(settings, "TEACHER_DEFAULT_PASSWORD", None)
        # 教室管理者は現時点で正規UIから共用初期パスワード付きで作成しない。
        # 権限が強いロールのため、新たな共用初期パスワードは追加せず、
        # 後続Issueでメール招待による本人パスワード設定へ寄せる。
        return None

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        user = self.instance

        if user.is_first_login:
            if not password:
                self.add_error("password", "初回ログイン時は、パスワードを必ず変更してください。")
                return cleaned_data

        if password:
            if len(password) < 8:
                self.add_error("password", "パスワードは8文字以上で入力してください。")
            if password != password_confirm:
                self.add_error("password_confirm", "パスワードが一致しません。")
            default_pw = self._get_role_default_password(user.role)
            if default_pw and password == default_pw:
                self.add_error("password", "そのパスワードは使用できません。")

        return cleaned_data

class StudentEditForTeachersForm(forms.ModelForm):
    """
    講師専用の教科書編集用フォーム
    """
    # 講師が担当生徒のパスワードを初期化するためのフラグ
    reset_password = forms.BooleanField(
        required=False,
        label="デフォルトパスワードにリセット"
    )
    class Meta:
        model = Student
        fields = ['textbook', 'email']
        labels = {
            'textbook': '使用教科書',
            'email': 'メールアドレス',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        textbook_qs = Textbook.objects.active()
        if self.instance and self.instance.textbook_id:
            textbook_qs = Textbook.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.textbook_id)
            )
        self.fields["textbook"].queryset = textbook_qs


class OrganizationCreateForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ['name']
        labels = {
            'name': '組織名',
        }

    def clean_name(self):
        """
        組織名が既に登録されていないかチェックする
        """
        name = self.cleaned_data.get('name')
        if Organization.objects.filter(name=name).exists():
            raise forms.ValidationError("この組織名は既に登録されています")
        return name


class StudentEmailRegistrationForm(forms.Form):
    """LINE経由メール登録フォーム。検証はフォーマットのみ、正規化・衝突チェックはサービス側で行う。"""
    email = forms.EmailField(
        label="メールアドレス",
        max_length=254,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "例: taro@example.com"}),
    )


class OrganizationAdminInvitationCreateForm(forms.Form):
    email = forms.EmailField(label="招待メールアドレス", max_length=254)


class OrganizationAdminInvitationAcceptForm(forms.Form):
    username = forms.CharField(
        label="ユーザー名",
        max_length=50,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    password = forms.CharField(
        label="パスワード",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "8文字以上のパスワードを入力",
            }
        ),
    )

    password_confirm = forms.CharField(
        label="確認用パスワード",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "確認用パスワードを入力",
            }
        ),
    )

    def _reject_whitespace(self, s: str, label: str) -> str:
        if any(ch in s for ch in ["\n", "\r", "\t", " "]):
            raise forms.ValidationError(f"{label}に空白や改行を含めないでください。")
        return s

    def clean_username(self):
        username = self.cleaned_data.get("username") or ""
        username = self._reject_whitespace(username, "ユーザー名")
        return username

    def clean_password(self):
        password = self.cleaned_data.get("password") or ""
        password = self._reject_whitespace(password, "パスワード")

        if len(password) < 8:  # 後々Django標準のパスワード認証と入れ替える機能
            raise forms.ValidationError("短すぎます。8文字以上入力してください。")

        return password

    def clean(self):
        cleaned = super().clean()

        password1 = cleaned.get("password")
        password2 = cleaned.get("password_confirm")
        if password1 and password2 and (password1 != password2):
            self.add_error("password_confirm", "確認用パスワードの値が一致しません。")

        return cleaned
