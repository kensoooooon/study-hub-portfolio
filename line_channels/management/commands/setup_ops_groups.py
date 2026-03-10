"""
GroupとPermissionを利用するために必要なセットアップを統一的に実施するためのコマンド
python manage.py setup_ops_groupsで実行


- django_content_type
appとmodelの組み合わせが1レコードずつ格納されている
id | application | model
6 | accounts | BaseUser
...
12 | vocab_trainer | EnglishWord
18 | line_channels | LineChannel

- auth_permission
上記を外部IDとして、権限の名前と略称を登録
id | name | codename | content_type_id
5 | CanViewLineChannel | view_linechannel | 18

上の2つを組み合わせて、モデルと権限の確認・管理を行う

ops_line_channelsグループは、閲覧+操作の両権限を持ち合わせている
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from line_channels.models import LineChannel


class Command(BaseCommand):
    help = "Create/update ops groups for LINE channel operations"

    def handle(self, *args, **options):
        # グループ名は運用で分かりやすい名前に固定
        group_name = "ops_line_channels"
        group, _ = Group.objects.get_or_create(name=group_name)  # グループの作成

        # LineChannel に紐づく permission を束ねる
        ct = ContentType.objects.get_for_model(LineChannel)

        codenames = [
            # Django標準
            "view_linechannel",
            "add_linechannel",
            "change_linechannel",
            # 独自
            "manage_line_channels",
            "view_line_channel_secret_metadata",
        ]

        perms = Permission.objects.filter(content_type=ct, codename__in=codenames) # LineChannelに紐づくpermissionをまとめる
        found = set(perms.values_list("codename", flat=True))  # 指定した権限以外
        missing = sorted(set(codenames) - found)

        if missing:
            self.stdout.write(self.style.WARNING(f"Missing permissions: {missing}"))
            self.stdout.write(self.style.WARNING("Did you run migrate?"))
            return

        # set() で完全同期（追加/削除差分の事故を防ぐ）
        group.permissions.set(perms)
        self.stdout.write(self.style.SUCCESS(f"Group '{group_name}' updated."))
        self.stdout.write(self.style.SUCCESS(f"Permissions: {', '.join(sorted(found))}"))
