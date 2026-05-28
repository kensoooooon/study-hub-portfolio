# accounts/tests/test_ops_organizations_permissions.py
from __future__ import annotations

from io import StringIO

from django.test import TestCase
from django.core.management import call_command, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.http import Http404

from accounts.models import Organization

# access_policies は本ブランチで追加した前提
from accounts.access_policies import (
    require_can_add_organization,
    require_can_assign_organization_administrator,
)


# -----------------------------
# 共通ヘルパ
# -----------------------------
def _create_user(*, email: str, role: str = "teacher", username: str = "U", password: str = "testpass123"):
    User = get_user_model()
    return User.objects.create_user(
        email=email,
        password=password,
        role=role,
        username=username,
    )


def _setup_ops_group() -> Group:
    call_command("setup_ops_organizations")
    return Group.objects.get(name="ops_organizations")


# ---------------------------------------------------------
# 管理コマンド: setup / give / revoke
# ---------------------------------------------------------
class OpsOrganizationsSetupCommandTests(TestCase):
    def test_setup_ops_organizations_creates_group_and_sets_expected_permissions(self):
        g = _setup_ops_group()

        # 期待する codename 一式
        expected = {
            "view_organization",
            "add_organization",
            "change_organization",
            "assign_organization_administrator",
        }
        actual = set(g.permissions.values_list("codename", flat=True))

        self.assertTrue(expected.issubset(actual), msg=f"missing={expected - actual}")

        # 逆に、意図しない権限が混ざっていないかの最低限チェック（delete は入れない方針）
        self.assertNotIn("delete_organization", actual)


class OpsOrganizationsGrantRevokeCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _create_user(email="ops@example.com", username="Ops")
        _setup_ops_group()

    def test_give_permission_adds_user_to_group_and_is_idempotent(self):
        out = StringIO()
        call_command("give_permission_manage_organization", "--email", "OPS@EXAMPLE.COM", stdout=out)
        self.assertTrue(self.user.groups.filter(name="ops_organizations").exists())

        # 2回目も成功（冪等）
        out2 = StringIO()
        call_command("give_permission_manage_organization", "--email", "ops@example.com", stdout=out2)
        self.assertTrue(self.user.groups.filter(name="ops_organizations").exists())

    def test_revoke_permission_removes_user_from_group_and_is_idempotent(self):
        g = Group.objects.get(name="ops_organizations")
        self.user.groups.add(g)

        out = StringIO()
        call_command("revoke_permission_manage_organization", "--email", "ops@example.com", stdout=out)
        self.assertFalse(self.user.groups.filter(name="ops_organizations").exists())

        # 2回目も成功（冪等）
        out2 = StringIO()
        call_command("revoke_permission_manage_organization", "--email", "ops@example.com", stdout=out2)
        self.assertFalse(self.user.groups.filter(name="ops_organizations").exists())

    def test_give_permission_raises_when_user_missing(self):
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command("give_permission_manage_organization", "--email", "missing@example.com", stdout=out)

    def test_revoke_permission_raises_when_user_missing(self):
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command("revoke_permission_manage_organization", "--email", "missing@example.com", stdout=out)

    def test_give_permission_accepts_case_insensitive_and_stripped_email_input(self):
        """
        運用でありがちな入力ミス（大文字/前後スペース）でも付与できることを担保する。
        email は save() で lower/strip 正規化され、DBも unique のため「曖昧に複数ヒット」は起きない前提。
        """
        out = StringIO()
        call_command("give_permission_manage_organization", "--email", "  OPS@EXAMPLE.COM  ", stdout=out)
        self.assertTrue(self.user.groups.filter(name="ops_organizations").exists())



# ---------------------------------------------------------
# access_policies: 権限チェック（404マスク）
# ---------------------------------------------------------
class OrganizationsAccessPoliciesTests(TestCase):
    def setUp(self):
        self.user_no_perms = _create_user(email="no@example.com", username="NoPerms")
        self.user_ops = _create_user(email="ops2@example.com", username="Ops2")

        # グループ付与で has_perm が通るようにする
        g = _setup_ops_group()
        self.user_ops.groups.add(g)

    def test_require_can_add_organization_denies_without_perm(self):
        with self.assertRaises(Http404):
            require_can_add_organization(self.user_no_perms)

    def test_require_can_add_organization_allows_with_perm(self):
        # 例外が出なければOK
        require_can_add_organization(self.user_ops)

    def test_require_can_assign_org_admin_denies_without_perm(self):
        with self.assertRaises(Http404):
            require_can_assign_organization_administrator(self.user_no_perms)

    def test_require_can_assign_org_admin_allows_with_perm(self):
        require_can_assign_organization_administrator(self.user_ops)
