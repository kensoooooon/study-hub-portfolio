import time
from django.core.management.base import BaseCommand
from vocab_trainer.models import WordMeaningRelation, WordMeaningRelationPartOfSpeech
from processors.example_sentence_processor import ExampleSentenceProcessor


class Command(BaseCommand):
    help = "WordMeaningRelation の空の例文を一括生成して登録"

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=500,
            help='1回の処理で更新する最大件数（デフォルト：500）'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        processor = ExampleSentenceProcessor()

        # 空の example_sentence を取得
        relations = WordMeaningRelation.objects.filter(example_sentence__isnull=True)[:limit]

        if not relations.exists():
            self.stdout.write(self.style.SUCCESS("✅ 更新対象のデータはありません。"))
            return

        total_count = relations.count()
        self.stdout.write(self.style.SUCCESS(f"📚 {total_count} 件のデータの例文生成を開始します..."))

        success_count = 0
        failure_count = 0

        for index, relation in enumerate(relations, start=1):
            # 品詞情報の取得
            parts_of_speech = ", ".join(
                [p.part_of_speech.display_name for p in relation.parts_of_speech.all()]
            )

            # 例文生成
            example_sentence = processor.generate_example_sentence(
                word=relation.english_word.word,
                japanese_meaning=relation.japanese_meaning.meaning,
                part_of_speech=parts_of_speech
            )

            # 生成結果の登録
            if example_sentence and "例文を生成できませんでした" not in example_sentence:
                relation.example_sentence = example_sentence
                relation.save()
                success_count += 1
                self.stdout.write(f"✅ [{index}/{total_count}] {relation.english_word.word} → 例文登録完了")
            else:
                failure_count += 1
                self.stdout.write(f"❗️ [{index}/{total_count}] {relation.english_word.word} → 例文生成失敗")

            # ✅ 100件ごとに進捗出力
            if index % 100 == 0 or index == total_count:
                self.stdout.write(
                    self.style.SUCCESS(f"🌟 進捗状況: {index}/{total_count} 件処理完了")
                )

            # API負荷軽減のための間隔
            time.sleep(1)

        self.stdout.write(self.style.SUCCESS(f"🎉 例文の一括登録が完了しました！成功: {success_count} 件 / 失敗: {failure_count} 件"))
