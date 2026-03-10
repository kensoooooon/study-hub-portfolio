# line_channels/tests/test_access_control.py
from __future__ import annotations

from django.test import TestCase
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission, AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.http import Http404

from line_channels.models import LineChannel
from line_channels.access_policies import (
    require_can_manage_line_channels_or_404,
    require_can_view_line_channel_secret_metadata_or_404,
)


class OpsAccessControlTests(TestCase):
    """
    ops-access-control ブランチの「認可の土台」を保証するテスト。

    目的:
    - Permission が存在すること（migrate で作られる前提）
    - setup_ops_groups が Group を作り、必要な Permission を付与すること
    - access_policies が「権限なし => 404」「権限あり => 通る」を保証すること
    """

    @classmethod
    def setUpTestData(cls):
        # Permission は ContentType + codename で一意に決まる
        cls.ct_linechannel = ContentType.objects.get_for_model(LineChannel)

        cls.perm_manage = Permission.objects.get(
            content_type=cls.ct_linechannel,
            codename="manage_line_channels",
        )
        cls.perm_view_secret_meta = Permission.objects.get(
            content_type=cls.ct_linechannel,
            codename="view_line_channel_secret_metadata",
        )

        # テスト用ユーザー（role はプロジェクトの制約に合わせて付ける）
        User = get_user_model()
        cls.user_no_perms = User.objects.create_user(
            email="no-perms@example.com",
            password="testpass123",
            role="teacher",
            username="No Perms",
        )
        cls.user_ops = User.objects.create_user(
            email="ops@example.com",
            password="testpass123",
            role="teacher",
            username="Ops User",
        )

    def test_setup_ops_groups_creates_group_and_assigns_permissions(self):
        """
        管理コマンドで ops_line_channels グループが生成・更新され、
        期待する権限が付与されること。
        """
        call_command("setup_ops_groups")

        g = Group.objects.get(name="ops_line_channels")

        # 独自権限
        self.assertTrue(g.permissions.filter(pk=self.perm_manage.pk).exists())
        self.assertTrue(g.permissions.filter(pk=self.perm_view_secret_meta.pk).exists())

        # 参考: 標準権限も付けている設計なら、最低限 view が入っていることを確認しておくと安心
        self.assertTrue(g.permissions.filter(codename="view_linechannel").exists())

        # ユーザーを ops グループに入れる
        self.user_ops.groups.add(g)

        # 付与後は user.has_perm で True になる
        self.assertTrue(self.user_ops.has_perm("line_channels.manage_line_channels"))
        self.assertTrue(self.user_ops.has_perm("line_channels.view_line_channel_secret_metadata"))

    def test_require_can_manage_line_channels_or_404_denies_anonymous_and_no_perms(self):
        """
        access_policies は「権限なしなら 404」で隠蔽する。
        """
        with self.assertRaises(Http404):
            require_can_manage_line_channels_or_404(AnonymousUser())

        with self.assertRaises(Http404):
            require_can_manage_line_channels_or_404(self.user_no_perms)

    def test_require_can_manage_line_channels_or_404_allows_ops_group_user(self):
        """
        ops_line_channels グループ付与済みユーザーは通る。
        """
        call_command("setup_ops_groups")
        g = Group.objects.get(name="ops_line_channels")
        self.user_ops.groups.add(g)

        # 例外が出なければOK
        require_can_manage_line_channels_or_404(self.user_ops)

    def test_require_can_view_secret_metadata_or_404(self):
        """
        secret の「メタ情報」閲覧権限のチェックも同様に 404 隠蔽。
        """
        with self.assertRaises(Http404):
            require_can_view_line_channel_secret_metadata_or_404(self.user_no_perms)

        call_command("setup_ops_groups")
        g = Group.objects.get(name="ops_line_channels")
        self.user_ops.groups.add(g)

        require_can_view_line_channel_secret_metadata_or_404(self.user_ops)
