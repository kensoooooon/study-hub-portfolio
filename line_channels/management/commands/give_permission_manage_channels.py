from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model


GROUP_NAME = "ops_line_channels"


class Command(BaseCommand):
    help = f"指定メールアドレスのユーザーを {GROUP_NAME} グループに追加する（冪等）"

    def add_arguments(self, parser):
        parser.add_argument("--email", type=str, required=True)

    def handle(self, *args, **options):
        User = get_user_model()
        email = User.objects.normalize_email((options["email"] or "").strip()).strip()

        if not email:
            raise CommandError("email が空です。--email を指定してください。")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError(f"{email} を持つユーザーは存在しません。")

        try:
            group = Group.objects.get(name=GROUP_NAME)
        except Group.DoesNotExist:
            raise CommandError(f"{GROUP_NAME} グループが存在しません。先に setup_ops_groups を実行してください。")

        if user.groups.filter(pk=group.pk).exists():
            self.stdout.write(self.style.WARNING(f"{user} は既に {GROUP_NAME} に所属しています。"))

        user.groups.add(group)
        self.stdout.write(self.style.SUCCESS(f"{user} を {GROUP_NAME} グループに追加しました。"))
