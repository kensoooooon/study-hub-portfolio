"""
2025/11/09
→StudentにOrganizationを外部モデルとして登録する
    ラインのマルチチャンネルに対応するために、「ある生徒は必ずいずれかの組織に所属している」という状態をキープ
    on_delete=models.PROTECTを使って、組織を誤って削除した際に全てのデータが消し飛ばないように手動で生徒を退会してからでないと、
    組織を削除できないようにしている
    
"""
import uuid

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings


from .organization_models import Classroom, Organization
from accounts.services.normalize_email import normalize_email


# Issue #162: is_superuser はテナント境界・権限をバイパスするため、本プロジェクトでは
# 一切許可しない。生成経路 (create_user / create_superuser / save()) で明示的に例外を
# 送出し、DB レベルでは BaseUser.Meta の CheckConstraint が最終防御となる。
IS_SUPERUSER_DISABLED_MSG = (
    "is_superuser=True のユーザーは作成できません "
    "(Issue #162: テナント境界・権限バイパス排除のため無効化済み)。"
)


class BaseUserManager(BaseUserManager):
    """
    カスタムユーザーのマネージャークラス
    """
    def create_user(self, email=None, password=None, **extra_fields):
        if extra_fields.get('is_superuser'):
            raise ValueError(IS_SUPERUSER_DISABLED_MSG)
        if not email and 'role' in extra_fields and extra_fields['role'] != 'student':
            raise ValueError("メールアドレスは生徒以外には必須です")
        if email:
            email = normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        # createsuperuser コマンド等から呼ばれた際に「なぜ失敗したか」を明示する。
        raise ValueError(IS_SUPERUSER_DISABLED_MSG)


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

    class Meta:
        constraints = [
            # Issue #162: is_superuser=True を DB レベルで一切許可しない。
            # Python 側のガード (create_user / create_superuser / save()) を
            # 経由しない queryset.update() / bulk_create() / bulk_update() /
            # 生 SQL も含めて拒否する最終防御。
            models.CheckConstraint(
                condition=models.Q(is_superuser=False),
                name="ck_baseuser_is_superuser_always_false",
            ),
        ]

    def clean(self):
        """
        バリデーション: 生徒以外はメールアドレスが必須
        """
        if not self.role:
            raise ValidationError("ユーザーの役割が設定されていません")
        if self.role != 'student' and not self.email:
            raise ValidationError(f"{self.get_role_display()}にはメールアドレスが必要です")
        self.email = normalize_email(self.email)

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

    def save(self, *args, **kwargs):
        # Issue #162: 全 MTI サブクラス (Student / Teacher / ClassroomAdministrator /
        # OrganizationAdministrator) の save() は super().save() 経由でここを通るため、
        # このガード 1 点で全書き込み経路 (create_user 含む) を塞げる。
        # save() を経由しない queryset.update() / bulk_create() 等は
        # BaseUser.Meta の CheckConstraint が DB レベルで拒否する。
        if self.is_superuser:
            raise ValueError(IS_SUPERUSER_DISABLED_MSG)
        self.email = normalize_email(self.email)
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # is_superuser による権限バイパスの無効化 (Issue #162)
    # ------------------------------------------------------------------
    # is_superuser は本来 2 箇所で「全権限」を与える:
    #   (1) PermissionsMixin.has_perm / has_module_perms の
    #       `if self.is_active and self.is_superuser: return True` 短絡
    #   (2) ModelBackend._get_permissions の
    #       `if user_obj.is_superuser: perms = Permission.objects.all()`
    # (1) を外すだけだと _user_has_perm 経由で (2) が到達可能になり、
    # 非オブジェクト権限チェックのバイパスが残る。ここでは (1)(2) の
    # どちらの superuser 分岐も通らず、明示付与された権限だけで判定する。
    # 非 superuser に対する評価は ModelBackend の通常評価
    # (user_permissions と group 経由 permission の合算) と一致する。
    #
    # 注意: obj 単位の権限を付与する認証 backend は本プロジェクトに存在
    # しない (AUTHENTICATION_BACKENDS 未設定 = ModelBackend のみ)。
    # 将来 AUTHENTICATION_BACKENDS にカスタム backend を追加する場合は
    # この実装の見直しが必要。
    def _explicit_permission_labels(self):
        """user_permissions と groups に明示付与された権限ラベル集合を返す。

        Returns:
            set[str]: "{app_label}.{codename}" 形式の権限ラベル集合。
                非アクティブユーザーは常に空集合。
        """
        if not self.is_active:
            return set()

        cache_attr = "_explicit_perm_label_cache"  # この属性が存在すればキャッシュを利用する
        if not hasattr(self, cache_attr):  # 初回のみ付与の動作
            from django.contrib.auth.models import Permission

            perms = (
                Permission.objects.filter(
                    models.Q(user=self) | models.Q(group__user=self)
                )
                .values_list("content_type__app_label", "codename")
                .order_by()
            )
            setattr(
                self,
                cache_attr,
                {f"{app_label}.{codename}" for app_label, codename in perms},
            )
        return getattr(self, cache_attr)

    def has_perm(self, perm, obj=None):
        """is_superuser による全権限付与を無効化した権限判定。

        Args:
            perm (str): "{app_label}.{codename}" 形式の権限。
            obj: オブジェクト単位判定の対象。本プロジェクトでは
                これを解決する backend が無いため、指定時は常に False。

        Returns:
            bool: 明示付与された権限に含まれる場合のみ True。
        """
        if not self.is_active:
            return False
        if obj is not None:
            return False
        return perm in self._explicit_permission_labels()

    def has_module_perms(self, app_label):
        """is_superuser による全権限付与を無効化した app 単位の権限判定。

        Args:
            app_label (str): 対象アプリのラベル。

        Returns:
            bool: 当該 app に明示付与された権限を 1 つ以上持つ場合のみ True。
        
        Notes:
            現在のプロジェクトにおいてはこちらのメソッドは利用されていない
            予防的措置である点に注意
        """
        if not self.is_active:
            return False
        prefix = f"{app_label}."
        return any(
            label.startswith(prefix) for label in self._explicit_permission_labels()
        )

    def get_all_permissions(self, obj=None):
        """is_superuser による全権限付与を無効化した全権限取得。

        Args:
            obj: オブジェクト単位判定の対象。本プロジェクトでは
                これを解決する backend が無いため、指定時は常に空集合。

        Returns:
            set[str]: "{app_label}.{codename}" 形式の権限ラベル集合。
                非アクティブユーザーは常に空集合。
            
        Notes:
            現在のプロジェクトにおいてはこちらのメソッドは利用されていない
            has_module_perms同様に予防的措置である点に留意すること
        """
        if not self.is_active:
            return set()
        if obj is not None:
            return set()
        return self._explicit_permission_labels()


class StudentQuerySet(models.QuerySet):
    """
    アクティブ、非アクティブそれぞれを返すためのヘルパー
    """
    def active(self):
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)

class StudentManager(BaseUserManager):
    """
    生徒専用のマネージャークラス
    """
    def get_queryset(self):
        """
        上のクエリセットを仲介する
        """
        return StudentQuerySet(self.model, using=self._db)
    
    def active(self):
        """
        アクティブなもののみ返す

        -> Student.objects.active()が使えるように
        """
        return self.get_queryset().active()

    def inactive(self):
        """
        非アクティブなもののみ返す
        """
        return  self.get_queryset().inactive()

    def get_or_create_user(self, line_user_id, **extra_fields):
        """LINEユーザーIDを元に、生徒が存在すれば取得し、存在しなければ作成する。

        Args:
            line_user_id: 生徒のLINEユーザーID
            **extra_fields: 新規作成時に設定する追加属性

        Raises:
            ValueError: LINEユーザーIDが与えられなかった場合

        Returns:
            tuple(Student, bool): 生徒と、新規作成されたかどうか

        Notes:
            - extra_fields は get_or_create() の defaults に渡される。
            - そのため organization_id などの属性は新規作成時のみ設定され、既存 Student には反映されない。
        """
        if not line_user_id:
            raise ValueError("LINEユーザーIDが必要です")

        student, created = self.get_or_create(
            line_user_id=line_user_id,
            defaults={
                "role": "student",
                **extra_fields,
            },
        )
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
        null=False,
        blank=False,
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
        self.save(update_fields=["password", "is_first_login"])

    def clean(self):
        """
        所属している組織と教室・講師の整合性が保たれているかを確認
        """
        super().clean()

        if self.organization and self.pk:
            # 既に保存済みの場合のみチェック（新規はまだM2Mが無いので）
            invalid_classrooms = self.classrooms.exclude(organization_id=self.organization_id)
            if invalid_classrooms.exists():
                raise ValidationError(
                    {"classrooms": "生徒の所属組織と異なる組織の教室が含まれています。"}
                )

            # 🔐 講師側の所属組織との整合性チェック
            invalid_teachers = self.teachers.exclude(organization_id=self.organization_id)
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
        null=False,
        blank=False,
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
            invalid_classrooms = self.classrooms.exclude(organization_id=self.organization_id)
            if invalid_classrooms.exists():
                raise ValidationError(
                    {"classrooms": "講師の所属組織と異なる組織の教室が含まれています。"}
                )

    def get_students(self):
        """
        担当生徒一覧かつ自身と同じ組織に所属している生徒を取得するメソッド
        """
        return self.students.filter(
            is_active=True,
            organization_id=self.organization_id,
        ).order_by('grade')

    def can_be_accessed_by(self, user):
        """
        ユーザーがこの講師にアクセスできるかを判定するメソッド
        """
        if user.role == 'organization_administrator':
            admin = user.get_role_object()
            if admin:
                # 講師が組織管理者が管理する教室に所属しているかを判定
                return self.classrooms.filter(organization_id=admin.organization_id).exists()
        elif user.role == 'classroom_administrator':
            admin = user.get_role_object()
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
        null=False,
        blank=False,
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
            invalid_classrooms = self.classrooms.exclude(organization_id=self.organization_id)
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
        if not student.is_active:
            return False
        return self.get_accessible_classrooms().filter(students=student).exists()



class OrganizationAdministrator(BaseUser):
    """
    組織管理者モデル
    """
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, null=False, blank=False,
        related_name='administrators', verbose_name="所属組織",
    )

    def save(self, *args, **kwargs):
        if not self.role:
            self.role = 'organization_administrator'
        super().save(*args, **kwargs)

    def can_manage_classroom(self, classroom: Classroom) -> bool:
        """
        自身の管理する組織に属する教室を管理できるかを判定
        """
        return self.organization_id == classroom.organization_id

    def get_accessible_classrooms(self):
        """
        管理可能なすべての教室を取得する（最適化されたクエリ）
        """
        return Classroom.objects.filter(organization_id=self.organization_id).select_related('organization')

    def can_manage_student(self, student: Student) -> bool:
        """
        特定の生徒に対して、それが自身の組織の教室に所属している管理対象であるかをチェック
        """
        if not student.is_active:
            return False
        return self.organization_id == student.organization_id
