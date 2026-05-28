"""
update_example_sentences

空の example_sentence を持つ WordMeaningRelation を対象に、
Claude API を使って例文を一括生成・登録するコマンドです。

APIコスト削減のため、デフォルトでは active な Textbook に紐づく
relation のみを対象とします。

================================================================================
オプション
================================================================================

--limit N
    1回の処理で更新する最大件数（デフォルト：500）

--include-inactive
    デフォルトでは active な Textbook に紐づく relation のみを対象とします。
    このオプションを指定すると、inactive Textbook にのみ紐づく relation も
    対象に加えます。

    ※ active / inactive の両方に紐づく relation は、デフォルトでも対象に含まれます。

================================================================================
使用例
================================================================================

# 通常実行（active Textbook に紐づく relation のみ、最大 500 件）
python manage.py update_example_sentences

# 件数を絞って試し実行（コスト・APIレート確認用）
python manage.py update_example_sentences --limit 10

# inactive Textbook にのみ紐づく relation も含めて実行
python manage.py update_example_sentences --include-inactive

# inactive も含めつつ件数を制限
python manage.py update_example_sentences --include-inactive --limit 50

================================================================================
"""

import time
from django.core.management.base import BaseCommand
from vocab_trainer.models import WordMeaningRelation, WordMeaningRelationPartOfSpeech
from processors.example_sentence_processor import ExampleSentenceProcessor


class Command(BaseCommand):
    help = (
        "WordMeaningRelation の空の例文を一括生成して登録。"
        "デフォルトは active Textbook に紐づく relation のみ対象（--include-inactive で全件）"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=500,
            help='1回の処理で更新する最大件数（デフォルト：500）'
        )
        parser.add_argument(
            '--include-inactive',
            action='store_true',
            default=False,
            help='inactive Textbook にのみ紐づく relation も対象に含める（デフォルト：除外）'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        include_inactive = options['include_inactive']
        processor = ExampleSentenceProcessor()

        # 空の example_sentence を持つ relation を絞り込む
        relations_qs = WordMeaningRelation.objects.filter(example_sentence__isnull=True)

        if not include_inactive:
            # active Textbook に紐づく relation のみ対象
            # （active / inactive 両方に紐づく relation は対象に含む）
            relations_qs = relations_qs.filter(
                contexts__chapter__textbook__is_active=True
            )

        relations_qs = (
            relations_qs
            .select_related("english_word", "japanese_meaning")
            .prefetch_related("parts_of_speech__part_of_speech")
            .distinct()  # 同一relationの重複処理を避ける
        )

        if not relations_qs.exists():
            self.stdout.write(self.style.SUCCESS("✅ 更新対象のデータはありません。"))
            return

        relations = list(relations_qs[:limit])
        total_count = len(relations)

        scope_label = "全 Textbook（inactive を含む）" if include_inactive else "active Textbook のみ"
        self.stdout.write(self.style.SUCCESS(
            f"📚 {total_count} 件のデータの例文生成を開始します...（対象スコープ: {scope_label}）"
        ))

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

            # 100件ごとに進捗出力
            if index % 100 == 0 or index == total_count:
                self.stdout.write(
                    self.style.SUCCESS(f"🌟 進捗状況: {index}/{total_count} 件処理完了")
                )

            # API負荷軽減のための間隔
            time.sleep(1)

        self.stdout.write(self.style.SUCCESS(
            f"🎉 例文の一括登録が完了しました！成功: {success_count} 件 / 失敗: {failure_count} 件"
        ))
