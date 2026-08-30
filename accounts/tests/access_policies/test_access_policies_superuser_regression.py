"""
accounts/access_policies.py で、is_superuser フラグによるアクセス制御バイパスが
発生しないことを確認する回帰テスト群。

背景 (Issue #162):
    - is_superuser をプロダクトから排除する方針となり、
      accounts/models/user_models.py の BaseUser で has_perm / has_module_perms /
      get_all_permissions をオーバーライドし、PermissionsMixin / ModelBackend が
      本来持つ「is_active かつ is_superuser なら全権限 True」という短絡を無効化した。
    - accounts/access_policies.py の require_* 関数は _require_perms_or_404() 経由で
      user.has_perm() を呼ぶだけなので、上記オーバーライドの結果として
      is_superuser=True でも明示付与された権限が無ければ Http404 になる
      （= superuser では短絡的に通らない）。

テスト手法:
    is_superuser=True の行は create_user / create_superuser / save() のガードと
    BaseUser.Meta の CheckConstraint により生成不可能なため、
    DB へは保存せずメモリ上でのみ user.is_superuser = True を立てて検証する。
"""

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.test import TestCase

from accounts.access_policies import (
    require_can_add_organization,
    require_can_invite_organization_administrator,
    require_can_view_organization,
)
from accounts.models import Organization, OrganizationAdministrator


def _grant_org_perm(user, codename: str) -> None:
    """Organization に対する指定 codename の権限を user に明示付与する。"""
    ct = ContentType.objects.get_for_model(Organization)
    perm = Permission.objects.get(content_type=ct, codename=codename)
    user.user_permissions.add(perm)


class SuperuserCannotBypassAccessPoliciesTestCase(TestCase):
    """
    accounts/access_policies.py の require_* 関数が、is_superuser フラグでは
    バイパスされないことを確認するテストケース。

    各テストでは DB に保存せずメモリ上で self.admin.is_superuser = True を立てる。
    """

    def setUp(self):
        self.org = Organization.objects.create(name="Org 1")
        # 権限は一切明示付与していない組織管理者
        self.admin = OrganizationAdministrator.objects.create(
            email="org_admin@example.com",
            username="OrgAdmin",
            role="organization_administrator",
            organization=self.org,
        )

    def test_require_can_add_organization_denies_superuser_without_explicit_perm(self):
        """
        is_superuser=True でも accounts.add_organization を明示付与されていなければ
        require_can_add_organization が Http404 を送出する（バイパス不可）ことを確認する回帰テスト。
        """
        self.admin.is_superuser = True  # DB へは保存しない

        with self.assertRaises(Http404):
            require_can_add_organization(self.admin)

    def test_require_can_view_organization_denies_superuser_without_explicit_perm(self):
        """
        is_superuser=True でも accounts.view_organization を明示付与されていなければ
        require_can_view_organization が Http404 を送出する（バイパス不可）ことを確認する回帰テスト。
        """
        self.admin.is_superuser = True  # DB へは保存しない

        with self.assertRaises(Http404):
            require_can_view_organization(self.admin)

    def test_require_can_invite_organization_administrator_denies_superuser_without_explicit_perm(self):
        """
        is_superuser=True でも accounts.invite_organization_administrator を
        明示付与されていなければ require_can_invite_organization_administrator が
        Http404 を送出する（バイパス不可）ことを確認する回帰テスト。
        """
        self.admin.is_superuser = True  # DB へは保存しない

        with self.assertRaises(Http404):
            require_can_invite_organization_administrator(self.admin)

    def test_has_perm_ignores_superuser_flag_for_access_policy_perms(self):
        """
        require_* の内部で使われる user.has_perm() が、is_superuser=True でも
        明示付与されていない権限に対して False を返すことを確認する回帰テスト。
        （require_* が Http404 になる根拠となる下位の挙動を固定する）
        """
        self.admin.is_superuser = True  # DB へは保存しない

        self.assertFalse(self.admin.has_perm("accounts.add_organization"))
        self.assertFalse(self.admin.has_perm("accounts.view_organization"))
        self.assertFalse(
            self.admin.has_perm("accounts.invite_organization_administrator")
        )

    def test_explicit_perm_grants_access_and_superuser_flag_is_irrelevant(self):
        """
        アクセス可否を決めるのは明示付与された権限であって is_superuser フラグではない
        ことを確認する。add_organization を明示付与すれば、is_superuser の有無に関わらず
        require_can_add_organization は例外を送出しない。

        （上の deny 系テストが「権限が無いから 404」であることを保証するための対照テスト）
        """
        _grant_org_perm(self.admin, "add_organization")
        # 明示付与のみで通ること（superuser フラグ無し）
        admin_without_flag = OrganizationAdministrator.objects.get(pk=self.admin.pk)
        require_can_add_organization(admin_without_flag)  # 例外が出なければ OK

        # is_superuser=True を立てても挙動は変わらない（通るものは通る）
        admin_with_flag = OrganizationAdministrator.objects.get(pk=self.admin.pk)
        admin_with_flag.is_superuser = True  # DB へは保存しない
        require_can_add_organization(admin_with_flag)  # 例外が出なければ OK
