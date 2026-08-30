"""
Issue #162: is_superuser によるテナント境界・権限バイパス排除のコア部分の回帰テスト。

対象:
- 生成ガード (BaseUserManager.create_user / create_superuser) 
- 保存ガード (BaseUser.save())
- BaseUser.Meta の CheckConstraint(is_superuser=False)
- BaseUser.has_perm / has_module_perms オーバーライド(PermissionsMixin と ModelBackend 双方の is_superuser 特例の無効化)
"""
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import BaseUser, Organization, Student, Teacher, ClassroomAdministrator, OrganizationAdministrator

from accounts.models.user_models import IS_SUPERUSER_DISABLED_MSG


class CreateGuardTests(TestCase):
    """生成経路で is_superuser=True が明示的に拒否されることを確認する回帰テスト。"""

    def test_create_user_with_is_superuser_true_raises(self):
        """
        BaseUser.objects.create_user(is_superuser=True) が ValueError となり、
        ユーザーが作成されないことを確認する。
        """
        with self.assertRaises(ValueError):
            BaseUser.objects.create_user(
                email="su@example.com",
                password="pass12345",
                username="su",
                role="organization_administrator",
                is_superuser=True,
            )
        self.assertFalse(BaseUser.objects.filter(email="su@example.com").exists())

    def test_create_superuser_always_raises(self):
        """
        BaseUser.objects.create_superuser() は常に ValueError となることを確認する。
        (createsuperuser コマンドから呼ばれても理由が分かるようにする)
        """
        with self.assertRaisesMessage(ValueError, IS_SUPERUSER_DISABLED_MSG):
            BaseUser.objects.create_superuser(
                email="su2@example.com", password="pass12345"
            )

    def test_save_rejects_is_superuser_true_for_baseuser_and_all_subclasses(self):
        """
        BaseUser および全 MTI サブクラスの save() で is_superuser=True が拒否され、
        DB 上のフラグが変化しないことを確認する。各サブクラスの save() が個別に
        super().save() (=BaseUser.save()) を経由することの回帰テスト。
        """
        org = Organization.objects.create(name="Org")
        cases = {
            BaseUser: dict(role="organization_administrator"),
            Student: dict(organization=org),
            Teacher: dict(organization=org),
            ClassroomAdministrator: dict(organization=org),
            OrganizationAdministrator: dict(organization=org),
        }
        for model_cls, extra in cases.items():
            with self.subTest(model=model_cls.__name__):
                name = model_cls.__name__.lower()
                obj = model_cls.objects.create(
                    email=f"{name}@example.com", username=name, **extra
                )
                obj.is_superuser = True
                with self.assertRaisesMessage(ValueError, IS_SUPERUSER_DISABLED_MSG):
                    obj.save()
                obj.refresh_from_db()
                self.assertFalse(obj.is_superuser)
    

class CheckConstraintTests(TestCase):
    """save() を経由しない書き込みも DB レベルで拒否されることを確認する回帰テスト。"""

    def test_queryset_update_to_is_superuser_true_raises_integrity_error(self):
        """
        queryset.update(is_superuser=True) は Python 側ガードを経由しないが、
        CheckConstraint により IntegrityError となることを確認する。
        """
        user = BaseUser.objects.create_user(
            email="upd@example.com",
            password="pass12345",
            username="upd",
            role="organization_administrator",
        )
        with self.assertRaisesMessage(IntegrityError, "ck_baseuser_is_superuser_always_false"):
            with transaction.atomic():
                BaseUser.objects.filter(pk=user.pk).update(is_superuser=True)


class HasPermOverrideTests(TestCase):
    """
    is_superuser フラグが立っていても has_perm / has_module_perms が
    全権限を返さないことを確認する回帰テスト。

    PermissionsMixin.has_perm の短絡を外すと ModelBackend._get_permissions の
    superuser 分岐が到達可能になるため、明示付与された権限のみで評価する。
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = BaseUser.objects.create_user(
            email="perm@example.com",
            password="pass12345",
            username="perm",
            role="organization_administrator",
        )
        ct = ContentType.objects.get_for_model(Organization)
        cls.granted_perm = Permission.objects.get(
            content_type=ct, codename="view_organization"
        )
        cls.user.user_permissions.add(cls.granted_perm)

    def _fresh_user(self):
        # ModelBackend / オーバーライドともにインスタンスに権限キャッシュを持つため、
        # 付与状態を反映するには取り直す。
        return BaseUser.objects.get(pk=self.user.pk)

    def test_explicitly_granted_permission_is_allowed(self):
        """
        明示付与された権限は is_superuser フラグの有無に関わらず True になることを確認する。
        """
        user = self._fresh_user()
        self.assertTrue(user.has_perm("accounts.view_organization"))

    def test_superuser_flag_does_not_grant_ungranted_permission(self):
        """
        メモリ上で is_superuser=True にしても、付与していない権限は False のままで
        あることを確認する (PermissionsMixin / ModelBackend 双方の特例の無効化)。
        """
        user = self._fresh_user()
        user.is_superuser = True
        self.assertFalse(user.has_perm("accounts.view_all_organizations"))
        self.assertFalse(user.has_perm("auth.add_user"))

    def test_superuser_flag_does_not_grant_module_perms_broadly(self):
        """
        is_superuser=True でも has_module_perms は明示付与のある app にのみ True、
        付与の無い app には False であることを確認する。
        """
        user = self._fresh_user()
        user.is_superuser = True
        self.assertTrue(user.has_module_perms("accounts"))  # view_organization を付与済み
        self.assertFalse(user.has_module_perms("auth"))

    def test_superuser_flag_still_denies_object_level_perm(self):
        """
        is_superuser=True でも obj 指定の has_perm は常に False であることを確認する。
        """
        org = Organization.objects.create(name="ObjOrg")
        user = self._fresh_user()
        user.is_superuser = True
        self.assertFalse(user.has_perm("accounts.view_organization", obj=org))

    def test_inactive_user_has_no_perms_even_with_grant(self):
        """
        非アクティブユーザーは明示付与があっても has_perm が False であることを確認する。
        """
        user = self._fresh_user()
        user.is_active = False
        self.assertFalse(user.has_perm("accounts.view_organization"))
