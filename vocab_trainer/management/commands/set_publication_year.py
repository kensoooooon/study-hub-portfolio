from django.core.management.base import BaseCommand
from vocab_trainer.models import Textbook


class Command(BaseCommand):
    help = "未設定のTextbookに対して一括で発行年 (publication_year) を指定する"

    def add_arguments(self, parser):
        parser.add_argument("--name", type=str, required=True, help="教科書名 (例: 'New Horizon')")
        parser.add_argument("--year", type=int, required=True, help="一括で設定する発行年 (例: 2021)")

    def handle(self, *args, **options):
        name = options["name"]
        year = options["year"]

        textbooks = Textbook.objects.filter(name=name, publication_year__isnull=True)
        count = textbooks.update(publication_year=year)

        self.stdout.write(self.style.SUCCESS(
            f"✅ {count} 件の教科書に発行年 {year} を設定しました（シリーズ名: {name}）"
        ))
