"""
Issue #162 回帰テスト: line_channels/selectors.py の各セレクターが is_superuser
フラグによってバイパスされないことを固定する。

背景:
    - accounts/models/user_models.py の BaseUser で has_perm をオーバーライドし、
      PermissionsMixin / ModelBackend が本来持つ
      「is_active かつ is_superuser なら全権限 True」という短絡を無効化した。
    - line_channels/selectors.py は is_superuser を直接見ておらず、
      group 所属 + permission のみで可視／操作対象スコープを決める。
      したがって is_superuser=True でもスコープは広がらない。

テスト手法:
    is_superuser=True の行は create_user / save() のガードと
    CheckConstraint により生成不可能なため、DB へは保存せず
    メモリ上のインスタンスにフラグを立てて検証する。
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from accounts.models import Organization
from line_channels.models import LineChannel
from line_channels.selectors import (
    manageable_organizations_for_line_channels,
    visible_line_channels_qs,
)


class LineChannelsSelectorsSuperuserRegressionTests(TestCase):
    """line_channels/selectors.py の各セレクターが is_superuser でバイパスされないことを確認する。"""

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="org1")
        cls.channel = LineChannel.objects.create(
            organization=cls.org,
            channel_id="ch-1",
            bot_user_id="U" + "a" * 32,
            is_active=True,
        )

        User = get_user_model()
        cls.user = User.objects.create_user(
            email="user@example.com",
            password="pass12345",
            role="teacher",
            username="User",
        )

        cls.ct_linechannel = ContentType.objects.get_for_model(LineChannel)

    def setUp(self):
        # 権限キャッシュを避けるため取り直し、is_superuser を立てる
        self.su_user = get_user_model().objects.get(pk=self.user.pk)
        self.su_user.is_superuser = True  # DB へは保存しない

    # ------------------------------------------------------------------
    # visible_line_channels_qs
    # ------------------------------------------------------------------
    def test_visible_line_channels_qs_denies_superuser_without_group_and_perm(self):
        """
        is_superuser=True でも ops_line_channels グループ非所属かつ
        line_channels.manage_line_channels 未付与なら、
        visible_line_channels_qs は空クエリセットを返す（バイパス不可）ことを確認する回帰テスト。
        """
        qs = visible_line_channels_qs(self.su_user)
        self.assertEqual(qs.count(), 0)

    def test_visible_line_channels_qs_denies_superuser_in_group_without_perm(self):
        """
        ops_line_channels グループに所属していても、そのグループ／ユーザーが
        manage_line_channels 権限を持たなければ、is_superuser=True でも
        visible_line_channels_qs は空クエリセットを返すことを確認する回帰テスト。

        is_superuser 短絡が有効だった頃は has_perm が True になり、
        グループ所属と組み合わせて全件が返っていた。その経路が塞がれたことを固定する。
        """
        group = Group.objects.create(name="ops_line_channels")  # 権限は付与しない
        self.su_user.groups.add(group)

        qs = visible_line_channels_qs(self.su_user)

        self.assertEqual(qs.count(), 0)

    def test_visible_line_channels_qs_allows_group_member_with_explicit_perm(self):
        """
        対照テスト: ops_line_channels グループ所属かつ manage_line_channels を
        明示付与されたユーザーは、is_superuser の有無に関わらず全件を取得できる。
        （上の deny 系が「権限が無いから空」であることを保証する）
        """
        group = Group.objects.create(name="ops_line_channels")
        perm = Permission.objects.get(
            content_type=self.ct_linechannel, codename="manage_line_channels"
        )
        group.permissions.add(perm)

        member = get_user_model().objects.get(pk=self.user.pk)
        member.groups.add(group)

        qs = visible_line_channels_qs(member)

        self.assertEqual(list(qs), [self.channel])

    # ------------------------------------------------------------------
    # manageable_organizations_for_line_channels
    # ------------------------------------------------------------------
    def test_manageable_organizations_denies_superuser_without_perm(self):
        """
        is_superuser=True でも line_channels.add_linechannel を明示付与されていなければ、
        manageable_organizations_for_line_channels は空クエリセットを返す（バイパス不可）
        ことを確認する回帰テスト。
        """
        qs = manageable_organizations_for_line_channels(self.su_user)
        self.assertEqual(qs.count(), 0)

    def test_manageable_organizations_uses_explicit_perm_not_superuser_flag(self):
        """
        対照テスト: 対象スコープを決めるのは line_channels.add_linechannel の明示付与で
        あって is_superuser フラグではない。明示付与すれば flag の有無に関わらず全組織を返す。
        """
        perm = Permission.objects.get(
            content_type=self.ct_linechannel, codename="add_linechannel"
        )

        granted = get_user_model().objects.get(pk=self.user.pk)
        granted.user_permissions.add(perm)

        # フラグ無しでも通る
        self.assertEqual(
            list(manageable_organizations_for_line_channels(granted)), [self.org]
        )

        # is_superuser=True を立てても挙動は変わらない
        granted_su = get_user_model().objects.get(pk=self.user.pk)
        granted_su.is_superuser = True  # DB へは保存しない
        self.assertEqual(
            list(manageable_organizations_for_line_channels(granted_su)), [self.org]
        )
