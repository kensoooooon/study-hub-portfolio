from django.contrib import admin
from vocab_trainer.models import EnglishWord, JapaneseMeaning
from vocab_trainer.models import WordMeaningRelation
from vocab_trainer.models import WordMeaningRelationDifficulty, QuizResult
from vocab_trainer.models import StudentContextProgress


@admin.register(EnglishWord)
class EnglishWordAdmin(admin.ModelAdmin):
    list_display = ("word",)


@admin.register(JapaneseMeaning)
class JapaneseMeaningAdmin(admin.ModelAdmin):
    list_display = ("meaning",)


@admin.register(WordMeaningRelation)
class WordMeaningRelationAdmin(admin.ModelAdmin):
    list_display = ("english_word", "japanese_meaning", "display_parts_of_speech")
    search_fields = ("english_word__word", "japanese_meaning__meaning")
    list_filter = ("parts_of_speech__part_of_speech",)  # 中間モデルを介したフィルタ

    def display_parts_of_speech(self, obj):
        return ", ".join([p.part_of_speech.display_name for p in obj.parts_of_speech.all()])
    display_parts_of_speech.short_description = "品詞"


@admin.register(WordMeaningRelationDifficulty)
class WordMeaningRelationDifficultyAdmin(admin.ModelAdmin):
    list_display = ('relation', 'difficulty', 'correct_count', 'total_count')
    search_fields = ('relation__english_word__word', 'relation__japanese_meaning__meaning')
    list_filter = ('difficulty',)


@admin.register(QuizResult)
class QuizResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'get_relation', 'is_correct', 'answered_at')
    search_fields = ('context__relation__english_word__word', 'context__relation__japanese_meaning__meaning', 'student__username')
    list_filter = ('is_correct', 'answered_at')

    def get_relation(self, obj):
        return obj.context.relation
    get_relation.short_description = "語義"


@admin.register(StudentContextProgress)
class StudentContextProgressAdmin(admin.ModelAdmin):
    list_display = ('student', 'get_textbook', 'get_chapter', 'get_word', 'accuracy_rate', 'review_priority')
    search_fields = ('student__username', 'context__relation__english_word__word', 'context__relation__japanese_meaning__meaning')

    def get_textbook(self, obj):
        return obj.context.chapter.textbook.name
    get_textbook.short_description = "教科書"

    def get_chapter(self, obj):
        return obj.context.chapter.title
    get_chapter.short_description = "チャプター"

    def get_word(self, obj):
        return obj.context.relation.english_word.word
    get_word.short_description = "英単語"
