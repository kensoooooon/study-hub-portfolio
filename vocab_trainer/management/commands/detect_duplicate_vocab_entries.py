from django.core.management.base import BaseCommand
from collections import defaultdict
from vocab_trainer.models import (
    WordMeaningContext,
    WordMeaningRelationPartOfSpeech,
)


class Command(BaseCommand):
    help = "完全に重複している英単語（スペル・意味・品詞・教科書・学年）を検出して出力する"

    def handle(self, *args, **options):
        duplicates = defaultdict(list)

        for context in WordMeaningContext.objects.select_related(
            "relation__english_word",
            "relation__japanese_meaning",
            "chapter__textbook"
        ).all():

            pos_qs = WordMeaningRelationPartOfSpeech.objects.filter(
                relation=context.relation
            ).select_related("part_of_speech")

            for pos in pos_qs:
                key = (
                    context.relation.english_word.word,
                    context.relation.japanese_meaning.meaning,
                    pos.part_of_speech.name,
                    context.chapter.textbook.name,
                    context.chapter.textbook.grade,
                    context.chapter.title
                )
                duplicates[key].append(context.id)

        self.stdout.write("重複チェック結果:\n")
        found = False
        for key, ids in duplicates.items():
            if len(ids) > 1:
                word, meaning, pos, textbook, grade = key
                self.stdout.write(f"- word='{word}', meaning='{meaning}', pos='{pos}', textbook='{textbook}', grade={grade} → 件数: {len(ids)}")
                found = True

        if not found:
            self.stdout.write("重複データは見つかりませんでした。")
