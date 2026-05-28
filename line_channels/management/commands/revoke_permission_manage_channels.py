from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model


GROUP_NAME = "ops_line_channels"


class Command(BaseCommand):
    help = f"指定メールアドレスのユーザーを {GROUP_NAME} から取り除く（冪等）"

    def add_arguments(self, parser):
        parser.add_argument("--email", type=str, required=True)

    def handle(self, *args, **options):
        User = get_user_model()
        raw = (options["email"] or "").strip()
        if not raw:
            raise CommandError("email が空です。--email を指定してください。")

        email = raw.strip()

        qs = User.objects.filter(email__iexact=email)

        if not qs.exists():
            raise CommandError(f"{email} を持つユーザーは存在しません。")

        if qs.count() > 1:
            # 万一のデータ不整合（過去データ/手動投入）を明示的に止める
            candidates = ", ".join(qs.values_list("email", flat=True))
            raise CommandError(
                f"{email} に一致するユーザーが複数存在します（大小無視）。DBを確認してください: {candidates}"
            )

        user = qs.get()

        try:
            group = Group.objects.get(name=GROUP_NAME)
        except Group.DoesNotExist:
            raise CommandError(f"{GROUP_NAME} グループが存在しません。先に setup_ops_groups を実行してください。")

        if not user.groups.filter(pk=group.pk).exists():
            self.stdout.write(self.style.WARNING(f"{user} は既に {GROUP_NAME} に所属していません。"))
            return

        user.groups.remove(group)
        self.stdout.write(self.style.SUCCESS(f"{user} を {GROUP_NAME} グループから除外しました。"))
