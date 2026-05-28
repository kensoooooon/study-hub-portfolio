"""
TSVファイル新規登録用

まだ存在していない教科書、年度、品詞に対してのみ登録作業を実施

- data全体からの読み取り
python manage.py import_vocab_data

- 特定ファイルからの読み取り
python manage.py import_vocab_data --file "data/vocab_trainer/New Horizon/2025年度/3年/名詞.tsv"

- 特定ディレクトリからの読み取り
eg. python manage.py import_vocab_data --dir "data/vocab_trainer/New Horizon/2025年度/3年"
"""

import os
import csv
import time
from pathlib import Path
from collections import defaultdict
from django.core.management.base import BaseCommand
from vocab_trainer.models import (
    EnglishWord, JapaneseMeaning, WordMeaningRelation,
    PartOfSpeech, WordMeaningRelationPartOfSpeech,
    Textbook, Chapter, WordMeaningContext,
    ContextPartOfSpeech
)

from .utils import load_chapter_orders, normalize_chapter_title, get_file_information, POS_DICT


class Command(BaseCommand):
    help = "data全体、もしくは特定ディレクトリ、あるいは特定ファイルから語彙データを読み込み登録する"

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='インポート対象のTSVファイルパス（相対または絶対パス）'
        )
        parser.add_argument(
            '--dir',
            type=str,
            help='インポート対象のディレクトリパス（相対または絶対パス）'
        )

    def handle(self, *args, **options):
        start_time = time.time()
        base_path = Path("data/vocab_trainer")
        self.chapter_orders = load_chapter_orders(base_path)

        if not self.chapter_orders:
            self.stdout.write(self.style.ERROR("❌ チャプターリストが見つかりません。インポートを中止します。"))
            return

        file_arg = options.get("file")
        dir_arg = options.get("dir")

        if file_arg:
            file_path = Path(file_arg)
            if not file_path.exists():
                self.stdout.write(self.style.ERROR(f"指定されたファイルが存在しません: {file_arg}"))
                return
            self.stdout.write(self.style.SUCCESS(f"単一ファイルインポート: {file_path}"))
            self.process_tsv(file_path)

        elif dir_arg:
            dir_path = Path(dir_arg)
            if not dir_path.exists() or not dir_path.is_dir():
                self.stdout.write(self.style.ERROR(f"指定ディレクトリが存在しません: {dir_arg}"))
                return
            file_list = [f for f in dir_path.glob("*.tsv") if f.name != "チャプターリスト.tsv"]
            total_files = len(file_list)
            self.stdout.write(self.style.SUCCESS(f"ディレクトリ一括インポート: {total_files} ファイル in {dir_path}"))

            for idx, file_path in enumerate(file_list, start=1):
                self.stdout.write(self.style.SUCCESS(f"処理中 {idx}/{total_files}: {file_path}"))
                self.process_tsv(file_path)

        else:
            file_list = [Path(root) / file for root, _, files in os.walk(base_path)
                        for file in files if file.endswith(".tsv") and file != "チャプターリスト.tsv"]
            total_files = len(file_list)
            self.stdout.write(f"全体インポート開始: {total_files} ファイル")

            for idx, file_path in enumerate(file_list, start=1):
                self.stdout.write(self.style.SUCCESS(f"処理中 {idx}/{total_files}: {file_path}"))
                self.process_tsv(file_path)

        elapsed = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(f"インポート完了: {elapsed:.2f} 秒"))

    def process_tsv(self, file_path):
        try:
            textbook_name, edition_str, grade_str, part_of_speech_jp = get_file_information(file_path)
        except Exception as e:
            print(f"ファイル処理失敗: {e}, ファイルパス: {file_path}")
            return
        
        try:
            publication_year = int(edition_str.replace("年度", ""))
            grade = int(grade_str[0])
        except ValueError:
            self.stdout.write(self.style.WARNING(f"スキップ: 年度または学年が取得できません: {file_path}"))
            return

        pos_en = POS_DICT.get(part_of_speech_jp)
        if not pos_en:
            self.stdout.write(self.style.WARNING(f"未定義の品詞: {part_of_speech_jp}"))
            return

        # 無効化状態の教科書は取り込みを行わない=更新が行われないとみなす
        inactive = Textbook.objects.inactive().filter(
            name=textbook_name,
            grade=grade,
            publication_year=publication_year,
        ).first()
        if inactive:
            self.stdout.write(self.style.WARNING(
                f"スキップ: '{textbook_name}' 中{grade}年（{publication_year}年度）は"
                f"無効状態のためインポートを中断します。"
            ))
            return

        textbook, _ = Textbook.objects.get_or_create(
            name=textbook_name,
            grade=grade,
            publication_year=publication_year,
            defaults={"publisher": "不明"}
        )
        part_of_speech, _ = PartOfSpeech.objects.get_or_create(name=pos_en, defaults={"display_name": part_of_speech_jp})

        existing_chapters = Chapter.objects.filter(textbook=textbook)
        already_registered = WordMeaningContext.objects.filter(
            chapter__in=existing_chapters,
            part_of_speeches__part_of_speech=part_of_speech
        ).exists()

        if already_registered:
            self.stdout.write(self.style.WARNING(
                f"スキップ: {textbook_name} 中{grade}年（{publication_year}年度, 品詞: {part_of_speech_jp}）のデータは既に存在します"
            ))
            return

        with open(file_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)

            for idx, row in enumerate(rows, start=1):
                word = row.get("英単語", "").strip()
                meanings_raw = row.get("意味", "").strip()
                chapter_title = row.get("チャプター名", "").strip()
                chapter_title = normalize_chapter_title(chapter_title)  # ← 追加

                if not word or not meanings_raw or not chapter_title:
                    self.stdout.write(self.style.WARNING(
                        f"⚠️ スキップ: {file_path.name} の {idx} 行目 - 不完全な行（word='{word}', meaning='{meanings_raw}', chapter='{chapter_title}'）"
                    ))
                    continue

                meanings = [m.strip() for m in meanings_raw.split(",") if m.strip()]
                if not meanings:
                    self.stdout.write(self.style.WARNING(
                        f"⚠️ スキップ: {file_path.name} の {idx} 行目 - 意味が空リスト（raw: '{meanings_raw}'）"
                    ))
                    continue

                self.stdout.write(f"  {idx}/{len(rows)} 単語処理中: {word}")

                try:
                    english_word, _ = EnglishWord.objects.get_or_create(word=word)

                    for meaning_text in meanings:
                        japanese_meaning, _ = JapaneseMeaning.objects.get_or_create(meaning=meaning_text)
                        relation, _ = WordMeaningRelation.objects.get_or_create(
                            english_word=english_word,
                            japanese_meaning=japanese_meaning
                        )
                        WordMeaningRelationPartOfSpeech.objects.get_or_create(
                            relation=relation,
                            part_of_speech=part_of_speech
                        )

                        chapter_order = self.chapter_orders[textbook_name][publication_year][grade].get(chapter_title, 999)
                        chapter, _ = Chapter.objects.get_or_create(
                            textbook=textbook,
                            title=chapter_title,
                            defaults={"order": chapter_order}
                        )

                        context, _ = WordMeaningContext.objects.get_or_create(
                            relation=relation,
                            chapter=chapter,
                            grade=grade
                        )

                        ContextPartOfSpeech.objects.get_or_create(
                            context=context,
                            part_of_speech=part_of_speech
                        )

                except Exception as inner_e:
                    self.stdout.write(self.style.ERROR(f"  エラー: {file_path} の {idx} 行目: {word} → {inner_e}"))
