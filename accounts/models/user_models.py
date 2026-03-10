"""
2025/11/09
→StudentにOrganizationを外部モデルとして登録する
    ラインのマルチチャンネルに対応するために、「ある生徒は必ずいずれかの組織に所属している」という状態をキープ
    on_delete=models.PROTECTを使って、組織を誤って削除した際に全てのデータが消し飛ばないように手動で生徒を退会してからでないと、
    組織を削除できないようにしている
    
"""
import uuid
from typing import Optional

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings


from .organization_models import Classroom, Organization




class BaseUserManager(BaseUserManager):
    """
    カスタムユーザーのマネージャークラス
    """
    def create_user(self, email=None, password=None, **extra_fields):
        if not email and 'role' in extra_fields and extra_fields['role'] != 'student':
            raise ValueError("メールアドレスは生徒以外には必須です")
        if email:
            email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'organization_administrator')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('スーパーユーザーはis_staff=Trueである必要があります')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('スーパーユーザーはis_superuser=Trueである必要があります')

        return self.create_user(email, password, **extra_fields)


class BaseUser(AbstractBaseUser, PermissionsMixin):
    """
    抽象ユーザーモデル（共通部分）
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, blank=True, null=True, verbose_name="メールアドレス")
    username = models.CharField(max_length=100, blank=True, null=True, verbose_name="名前")
    is_active = models.BooleanField(default=True, verbose_name="有効")
    is_staff = models.BooleanField(default=False, verbose_name="スタッフ権限")
    is_superuser = models.BooleanField(default=False, verbose_name="スーパーユーザー権限")
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name="登録日")
    role = models.CharField(
        max_length=50,
        choices=[
            ('student', '生徒'),
            ('teacher', '講師'),
            ('classroom_administrator', '教室管理者'),
            ('organization_administrator', '組織管理者'),
        ],
        verbose_name="役割"
    )
    is_first_login = models.BooleanField(default=True, verbose_name="初回ログインフラグ")

    objects = BaseUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def clean(self):
        """
        バリデーション: 生徒以外はメールアドレスが必須
        """
        if not self.role:
            raise ValidationError("ユーザーの役割が設定されていません")
        if self.role != 'student' and not self.email:
            raise ValidationError(f"{self.get_role_display()}にはメールアドレスが必要です")
        self.email = self._normalize_email(self.email)

    def __str__(self):
        return self.username or "未登録"

    def get_role_object(self):
        """
        ユーザーのロールに応じたオブジェクトを取得する
        """
        role_mapping = {
            'organization_administrator': 'organizationadministrator',
            'classroom_administrator': 'classroomadministrator',
            'teacher': 'teacher',
            'student': 'student',
        }
        related_name = role_mapping.get(self.role)
        if related_name:
            return getattr(self, related_name, None)
        return None
    
    def _normalize_email(self, email: str | None ) -> str | None:
        """メールアドレスをすべて小文字にする正規化を実施するための関数

        Args:
            email (str | None): 対象となるメールアドレス

        Returns:
            str | None: 正規化されたメールアドレス
        """
        if email is None:
            return None
        
        if not isinstance(email, str):
            return None
        
        stripped_email = email.strip()
        if stripped_email == "":
            return ""
        
        return stripped_email.lower()

    def save(self, *args, **kwargs):
        self.email = self._normalize_email(self.email)
        super().save(*args, **kwargs)


class StudentManager(BaseUserManager):
    """
    生徒専用のマネージャークラス
    """
    def get_or_create_user(self, line_user_id, **extra_fields):
        """
        LINEユーザーIDをもとに生徒を取得または作成
        """
        if not line_user_id:
            raise ValueError("LINEユーザーIDが必要です")

        student, created = self.get_or_create(line_user_id=line_user_id, defaults={
            'role': 'student',
            **extra_fields
        })
        return student, created


class GradeChoices(models.IntegerChoices):
    PRE_SCHOOL = 0, _('未就学児')
    ELEMENTARY_1 = 1, _('小学1年生')
    ELEMENTARY_2 = 2, _('小学2年生')
    ELEMENTARY_3 = 3, _('小学3年生')
    ELEMENTARY_4 = 4, _('小学4年生')
    ELEMENTARY_5 = 5, _('小学5年生')
    ELEMENTARY_6 = 6, _('小学6年生')
    JUNIOR_HIGH_1 = 7, _('中学1年生')
    JUNIOR_HIGH_2 = 8, _('中学2年生')
    JUNIOR_HIGH_3 = 9, _('中学3年生')
    HIGH_1 = 10, _('高校1年生')
    HIGH_2 = 11, _('高校2年生')
    HIGH_3 = 12, _('高校3年生')
    GAP_YEAR = 13, _('浪人生')
    WORKING = 14, _('社会人')


class Student(BaseUser):
    """生徒を表すモデル

    Fields:
        grade (models.IntegerField): 学年(選択型)
        teachers (models.ManyToManyField): 担当講師(複数想定)
        classrooms (models.ManyToManyField): 所属教室(複数想定)
        line_user_id (models.CharField): LineユーザーID。生徒の識別の大元であるため、いずれかの段階でblank, nullをFalseへ
        textbook (models.ForeignKey): 利用している教科書(単一想定)
        organization (models.ForeignKey): 所属している組織(単一想定)

    Raises:
        ValidationError: 自身の所属している組織に存在していない教室に所属している際に送出
    """
    grade = models.IntegerField(
        choices=GradeChoices.choices,
        verbose_name="学年",
        blank=True,
        null=True
    )
    teachers = models.ManyToManyField(
        'Teacher',
        related_name='students',
        blank=True,
        verbose_name="担当講師"
    )
    classrooms = models.ManyToManyField(
        'Classroom',
        related_name='students',
        blank=True,
        verbose_name="所属教室"
    )
    line_user_id = models.CharField(
        max_length=100, 
        unique=True, 
        blank=True, 
        null=True, 
        verbose_name="LINEユーザーID"
    )
    textbook = models.ForeignKey(
        'vocab_trainer.Textbook',  # ← 文字列にすることで循環を回避
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="使用教科書"
    )
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.PROTECT,  # 誤操作時に巻き込まれた削除されてしまうのを防止する
        null=True, blank=True,  # 既存データの移行が済んだら、両方Falseが望ましい
        related_name='students',
        verbose_name='所属組織'
    )
    objects = StudentManager()
    
    def save(self, *args, **kwargs):
        self.role = 'student'  # 保存時に role を強制設定
        super().save(*args, **kwargs)

    def set_default_password(self):
        """ 生徒のパスワードをデフォルト値に設定 """
        default_password = settings.STUDENT_DEFAULT_PASSWORD  # settings.py の値を取得
        self.set_password(default_password)  # 適宜変更
        self.is_first_login = True  # ⭐ 初回ログイン状態に戻す
        self.save()

    def clean(self):
        """
        所属している組織と教室・講師の整合性が保たれているかを確認
        """
        super().clean()

        if self.organization and self.pk:
            # 既に保存済みの場合のみチェック（新規はまだM2Mが無いので）
            invalid_classrooms = self.classrooms.exclude(organization=self.organization)
            if invalid_classrooms.exists():
                raise ValidationError(
                    {"classrooms": "生徒の所属組織と異なる組織の教室が含まれています。"}
                )

            # 🔐 講師側の所属組織との整合性チェック(担当とされる講師から、自身と同じ組織の所属するもの+所属組織がないものを弾く)
            invalid_teachers = self.teachers.exclude(
                models.Q(organization=self.organization) |
                models.Q(organization__isnull=True)  # ← 既存データ移行中は None は許容
            )
            if invalid_teachers.exists():
                raise ValidationError(
                    {"teachers": "生徒の所属組織と異なる組織の講師が含まれています。"}
                )


class Teacher(BaseUser):
    """
    講師モデル
    """
    classrooms = models.ManyToManyField(
        'Classroom',
        related_name='teachers',
        blank=False,
        verbose_name="担当教室"
    )
    # 単一組織への所属を前提とした属性
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.PROTECT,
        null=True, blank=True,  # 既存データ移行が済んだら False / False にしたい
        related_name='teachers',
        verbose_name='所属組織'
    )

    def save(self, *args, **kwargs):
        if not self.role:
            self.role = 'teacher'
        super().save(*args, **kwargs)

    def clean(self):
        """
        所属している組織と教室の整合性が保たれているかを確認
        """
        super().clean()

        if self.organization and self.pk:
            invalid_classrooms = self.classrooms.exclude(organization=self.organization)
            if invalid_classrooms.exists():
                raise ValidationError(
                    {"classrooms": "講師の所属組織と異なる組織の教室が含まれています。"}
                )

    def get_students(self):
        """
        担当生徒一覧を取得するメソッド
        """
        return self.students.order_by('grade')

    def can_be_accessed_by(self, user):
        """
        ユーザーがこの講師にアクセスできるかを判定するメソッド
        """
        if user.role == 'organization_administrator':
            admin = getattr(user, 'organizationadministrator', None)
            if admin:
                # 講師が組織管理者が管理する教室に所属しているかを判定
                return self.classrooms.filter(organization__in=admin.organizations.all()).exists()
        elif user.role == 'classroom_administrator':
            admin = getattr(user, 'classroomadministrator', None)
            if admin:
                # 教室管理者が管理する教室に講師が所属しているかを判定
                return self.classrooms.filter(id__in=admin.classrooms.values_list('id', flat=True)).exists()
        return False

    def set_default_password(self):
        """ 講師のパスワードをデフォルト値に設定 """
        default_password = settings.TEACHER_DEFAULT_PASSWORD  # settings.py の値を取得
        self.set_password(default_password)  # 適宜変更
        self.is_first_login = True  # ⭐ 初回ログイン状態に戻す
        self.save()

    def can_manage_student(self, student):
        """
        特定の生徒に対して、自身がアクセス可能かどうかを判定
        """
        return student in self.get_students()


class ClassroomAdministrator(BaseUser):
    """
    教室管理者モデル
    """
    classrooms = models.ManyToManyField(
        'Classroom',
        related_name='administrators',
        blank=True,
        verbose_name="管理教室"
    )
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.PROTECT,
        null=True, blank=True,  # 移行完了後に False / False へ
        related_name='classroom_administrators',
        verbose_name='所属組織'
    )

    def save(self, *args, **kwargs):
        if not self.role:
            self.role = 'classroom_administrator'
        super().save(*args, **kwargs)

    def clean(self):
        """
        所属している組織と教室の整合性を確認
        """
        super().clean()
        if self.organization and self.pk:
            invalid_classrooms = self.classrooms.exclude(organization=self.organization)
            if invalid_classrooms.exists():
                raise ValidationError(
                    {"classrooms": "教室管理者の所属組織と異なる組織の教室が含まれています。"}
                )

    def can_manage_classroom(self, classroom: Classroom) -> bool:
        """
        教室管理者が特定の教室を管理できるかを判定

        Args:
            classroom (Classroom): 判定対象の教室
        Returns:
            bool: 管理可能な場合は True、そうでない場合は False
        """
        return self.classrooms.filter(id=classroom.id).exists()
    
    def get_accessible_classrooms(self):
        """
        管理可能な教室を全て渡す
        """
        return self.classrooms.all()

    def can_manage_student(self, student: Student) -> bool:
        """
        特定の生徒に対して、その教室管理者が管理している教室に所属していて管理対象なのかをチェック
        """
        return self.get_accessible_classrooms().filter(students=student).exists()



class OrganizationAdministrator(BaseUser):
    """
    組織管理者モデル
    """
    organizations = models.ManyToManyField(
        Organization, related_name='administrators', blank=True, verbose_name="管理組織"
    )

    def save(self, *args, **kwargs):
        if not self.role:
            self.role = 'organization_administrator'
        super().save(*args, **kwargs)

    def can_manage_classroom(self, classroom: Classroom) -> bool:
        """
        自身の管理する組織に属する教室を管理できるかを判定
        """
        return self.organizations.filter(id=classroom.organization_id).exists()

    def get_accessible_classrooms(self):
        """
        管理可能なすべての教室を取得する（最適化されたクエリ）
        """
        return Classroom.objects.filter(organization__in=self.organizations.all()).select_related('organization')

    def get_accessible_organizations(self):
        """
        管理可能なすべての組織を取得する
        """
        return self.organizations.all()

    def can_manage_student(self, student: Student) -> bool:
        """
        特定の生徒に対して、それが自身の組織の教室に所属している管理対象であるかをチェック
        """
        # 1) 組織が確定している生徒は organization で判定（推奨）
        if student.organization_id:
            return self.organizations.filter(id=student.organization_id).exists()

        # 2) フォールバック：教室経由（既存ロジック）
        return self.get_accessible_classrooms().filter(students=student).exists()
