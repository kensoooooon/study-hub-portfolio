from django import forms
from django.conf import settings
from django.db.models import Q
from django.forms import CheckboxSelectMultiple
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

        # if student.organization is None:
        #     # 旧データ移行中だけ許容するならここでは弾かず、saveで補完
        #     return cleaned_data

        if student.organization_id != classroom.organization_id:
            raise forms.ValidationError(
                "生徒の所属組織と教室の所属組織が一致していません。"
            )

        return cleaned_data

    def save(self):
        student: Student = self.cleaned_data["student"]
        classroom: Classroom = self.cleaned_data["classroom"]

        if student.organization is None:
            student.organization = classroom.organization
            student.save(update_fields=["organization"])

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


class OrganizationAdminSelectForm(forms.Form):
    """
    組織に割り当てる OrganizationAdministrator を複数選択するフォーム。
    queryset は View 側から注入する（改ざん耐性のため）。

    form.is_valid()
    ↓
    form.full_clean()
    ↓
    1) 各フィールドのバリデーション
    2) clean_<fieldname>()
    3) form.clean()

    """
    admins = forms.ModelMultipleChoiceField(
        queryset=OrganizationAdministrator.objects.none(),
        required=True,
        widget=CheckboxSelectMultiple,
        label="割り当てる組織管理者",
    )

    def __init__(self, *args, candidate_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        if candidate_qs is None:
            candidate_qs = OrganizationAdministrator.objects.none()
        self.fields["admins"].queryset = candidate_qs

    def clean_admins(self):
        admins = self.cleaned_data["admins"]
        # 任意: 件数上限（事故防止・UI崩壊防止）
        MAX_ASSIGN = 20
        if admins.count() > MAX_ASSIGN:
            raise forms.ValidationError(f"一度に割り当てられる人数は最大 {MAX_ASSIGN} 人です。")
        return admins


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
