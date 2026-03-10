from django import forms
from accounts.models import BaseUser,Student, Teacher, OrganizationAdministrator, ClassroomAdministrator
from accounts.models import Classroom

from django.core.exceptions import ValidationError

from django import forms
from .models import Classroom

from vocab_trainer.models import Textbook

from django.conf import settings

from django.contrib.auth.hashers import check_password


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
        queryset=ClassroomAdministrator.objects.all(),
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
            admin = getattr(self.current_user, 'organizationadministrator', None)
            if admin:
                self.fields['administrators'].queryset = ClassroomAdministrator.objects.filter(
                    classrooms__organization__in=admin.organizations.all()
                )
        else:
            del self.fields['administrators']  # 教室管理者には表示しない


class AssignClassroomForm(forms.Form):
    """
    生徒割り当て用フォーム
    """
    student = forms.ModelChoiceField(queryset=Student.objects.none())
    classroom = forms.ModelChoiceField(queryset=Classroom.objects.none())

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop("current_user", None)
        super().__init__(*args, **kwargs)

        # 組織管理者以外から呼ばれるケースは想定しないが、一応ガード
        if not self.current_user or self.current_user.role != "organization_administrator":
            return

        org_admin: OrganizationAdministrator = self.current_user.get_role_object()
        if not org_admin:
            return

        managed_orgs = org_admin.organizations.all()

        # 🔐 管理している組織に属する生徒のみ
        self.fields["student"].queryset = Student.objects.filter(
            organization__in=managed_orgs,
            classrooms__isnull=True,
            line_user_id__isnull=False,
        )

        # 🔐 管理している組織に属する教室のみ
        self.fields["classroom"].queryset = Classroom.objects.filter(
            organization__in=managed_orgs
        )

    def save(self):
        student: Student = self.cleaned_data["student"]
        classroom: Classroom = self.cleaned_data["classroom"]

        # 🛡 最終防衛：所属組織の整合性チェック
        if student.organization is None:
            # 旧データなどで organization 未設定の場合は、ここで教室に合わせて設定する方針
            student.organization = classroom.organization
            student.save(update_fields=["organization"])
        elif student.organization_id != classroom.organization_id:
            # 「生徒の所属組織が正」なので、矛盾があれば教室側の設定ミスとして弾く
            raise ValidationError(
                "生徒の所属組織と教室の所属組織が一致していません。"
            )

        student.classrooms.add(classroom)
        return student


class StudentEditForm(forms.ModelForm):
    textbook = forms.ModelChoiceField(
        queryset=Textbook.objects.all(),
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
                managed_orgs = role_obj.organizations.all()
                qs = Teacher.objects.filter(
                    organization__in=managed_orgs
                )

            elif role == "classroom_administrator" and isinstance(role_obj, ClassroomAdministrator):
                # 管理している教室に所属している講師のみ
                qs = Teacher.objects.filter(
                    classrooms__in=role_obj.classrooms.all()
                )

        # さらに「生徒の所属組織」に絞る（二重チェック）
        if self.student and self.student.organization_id:
            qs = qs.filter(organization=self.student.organization)

        self.fields["teachers"].queryset = qs.distinct()


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
        teacher = super().save(commit=False)
        password = self.cleaned_data.get("password")
        classrooms = self.cleaned_data.get("classrooms")  # 修正ポイント

        if password:
            teacher.set_password(password)
        else:
            teacher.set_default_password()

        if classrooms:
            org = classrooms[0].organization
            teacher.organization = org

        if commit:
            teacher.save()
            teacher.classrooms.set(classrooms)  # 教室を適切に紐付ける
        return teacher

    def clean(self):
        cleaned_data = super().clean()
        self.instance.role = 'teacher'  # 新規作成時にroleを補完
        return cleaned_data

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
        help_text="空白の場合は変更されません"
    )

    class Meta:
        model = BaseUser
        fields = ['email', 'password']
        labels = {
            'email': 'メールアドレス'
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")

        if password:  # 空でない場合のみセット
            user.set_password(password)
        else:
            # 再取得して現在のハッシュ値を維持
            current_password = BaseUser.objects.get(pk=user.pk).password
            user.password = current_password
        if commit:
            user.save()
        return user

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")

        default_passwords = [
            getattr(settings, "STUDENT_DEFAULT_PASSWORD", ""),
            getattr(settings, "TEACHER_DEFAULT_PASSWORD", "")
        ]

        # 🔒 初回ログイン時には強制的にパスワード変更を要求
        if self.instance.is_first_login:
            if not password:
                raise ValidationError("初回ログイン時は、パスワードを必ず変更してください。")
            if password in default_passwords:
                raise ValidationError("初回ログイン時には、デフォルトパスワード以外を設定してください。")
        else:
            # 通常時でもデフォルトパスワードは禁止（任意）
            if password and password in default_passwords:
                raise ValidationError("デフォルトパスワードと同じパスワードには変更できません。")

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
