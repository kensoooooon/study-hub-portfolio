"""
英単語学習をサポートするデータ構造

EnglishWord（英単語）
 └── WordMeaningRelation（語義：英単語×日本語）
       ├── JapaneseMeaning（日本語訳）
       ├── WordMeaningRelationPartOfSpeech（辞書的品詞 M:N）
       │     └── PartOfSpeech（品詞名・表示名）
       ├── WordMeaningRelationDifficulty（語義単位の全体難易度）
       └── WordMeaningContext（教科書文脈：語義×チャプター）
             ├── Chapter（教科書の章）
             │     └── Textbook（教科書＋出版社＋学年）
             ├── ContextPartOfSpeech（文脈ごとの品詞）
             ├── StudentContextProgress（生徒×文脈の学習進捗）
             └── QuizResult（生徒×文脈のクイズ履歴）

"""

from django.db import models
from django.utils import timezone

from accounts.models import Student

from datetime import timedelta


class EnglishWord(models.Model):
    word = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.word


class JapaneseMeaning(models.Model):
    meaning = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.meaning


class WordMeaningRelation(models.Model):
    english_word = models.ForeignKey(EnglishWord, on_delete=models.CASCADE, related_name="meanings")
    japanese_meaning = models.ForeignKey(JapaneseMeaning, on_delete=models.CASCADE, related_name="english_words")
    example_sentence = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.english_word.word} → {self.japanese_meaning.meaning}"


class PartOfSpeech(models.Model):
    name = models.CharField(max_length=50, unique=True)  # e.g. "noun"
    display_name = models.CharField(max_length=50)       # e.g. "名詞"

    def __str__(self):
        return self.display_name


class WordMeaningRelationPartOfSpeech(models.Model):
    relation = models.ForeignKey(WordMeaningRelation, on_delete=models.CASCADE, related_name="parts_of_speech")
    part_of_speech = models.ForeignKey(PartOfSpeech, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('relation', 'part_of_speech')

    def __str__(self):
        return f"{self.relation} ({self.part_of_speech.display_name})"


class WordMeaningRelationDifficulty(models.Model):
    relation = models.OneToOneField(WordMeaningRelation, on_delete=models.CASCADE, related_name="difficulty")
    correct_count = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)
    difficulty = models.FloatField(default=1.0)

    def update_difficulty(self):
        if self.total_count > 0:
            correct_rate = self.correct_count / self.total_count
            self.difficulty = 1.0 - correct_rate
        else:
            self.difficulty = 1.0
        self.save()

    def __str__(self):
        return f"{self.relation} - 難易度: {self.difficulty:.2f}"


class Textbook(models.Model):
    name = models.CharField(max_length=100)
    publisher = models.CharField(max_length=100)
    grade = models.PositiveSmallIntegerField()
    publication_year = models.PositiveIntegerField(null=True, blank=True)  # ← 最初はオプションとして追加

    class Meta:
        unique_together = ('name', 'grade', 'publication_year')

    def __str__(self):
        year_display = f"（{self.publication_year}年度）" if self.publication_year else ""
        return f"{self.name} (中{self.grade}年){year_display}"


class Chapter(models.Model):
    textbook = models.ForeignKey(Textbook, on_delete=models.CASCADE, related_name="chapters")
    title = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField()

    def __str__(self):
        return f"{self.textbook} - {self.title}"

    def get_progress_for_student(self, student):
        contexts = self.meaning_contexts.all()
        total = contexts.count()

        progress_qs = StudentContextProgress.objects.filter(
            student=student,
            context__in=contexts
        ).select_related('context')

        learned = progress_qs.filter(total_count__gt=0).distinct().count()

        category_counts = {'stable': 0, 'warning': 0, 'danger': 0}
        for progress in progress_qs:
            category = progress.get_review_priority_category()
            category_counts[category] += 1

        # retention_ratio を計算
        if total > 0:
            ratio = {
                'stable': round(category_counts['stable'] / total * 100, 1),
                'warning': round(category_counts['warning'] / total * 100, 1),
                'danger': round(category_counts['danger'] / total * 100, 1),
            }
        else:
            ratio = None

        percent = round((learned / total) * 100, 1) if total > 0 else 0.0

        return {
            'total': total,
            'learned': learned,
            'percentage': percent,
            'retention': category_counts,
            'retention_ratio': ratio  # retention比率を明示的に返す（テンプレート用）
        }


class WordMeaningContext(models.Model):
    relation = models.ForeignKey(WordMeaningRelation, on_delete=models.CASCADE, related_name="contexts")
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="meaning_contexts")
    grade = models.PositiveSmallIntegerField()

    def __str__(self):
        return f"{self.relation.english_word.word} ({self.grade}年) in {self.chapter}"


class ContextPartOfSpeech(models.Model):
    context = models.ForeignKey(WordMeaningContext, on_delete=models.CASCADE, related_name="part_of_speeches")
    part_of_speech = models.ForeignKey(PartOfSpeech, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("context", "part_of_speech")

    def __str__(self):
        return f"{self.context} ({self.part_of_speech.display_name})"


class StudentContextProgress(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="context_progress")
    context = models.ForeignKey(WordMeaningContext, on_delete=models.CASCADE, related_name="student_progress")

    correct_count = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)
    accuracy_rate = models.FloatField(default=0.0)
    last_answered_at = models.DateTimeField(null=True, blank=True)
    review_priority = models.FloatField(default=1.0)
    ease_factor = models.FloatField(default=2.5)
    interval = models.PositiveIntegerField(default=1)
    # 将来的なsm-2導入への布石
    next_due_at = models.DateTimeField(null=True, blank=True)
    repetition_count = models.IntegerField(default=0)
    last_is_correct = models.BooleanField(null=True, blank=True)

    def update_progress(self, is_correct):
        self.total_count += 1
        if is_correct:
            self.correct_count += 1
            if self.last_is_correct:
                self.repetition_count += 1
            else:
                self.repetition_count = 1
        else:
            self.repetition_count = 0

        self.last_is_correct = is_correct
        self.accuracy_rate = self.correct_count / self.total_count if self.total_count > 0 else 0.0
        self.last_answered_at = timezone.now()
        
        self.update_review_priority(is_correct)
        self.schedule_next_due(is_correct)
        self.save()

    def update_review_priority(self, is_correct):
        if is_correct:
            self.ease_factor = max(1.3, self.ease_factor - 0.2 + (0.1 * (5 - (1.0 - self.accuracy_rate) * 5)))
            self.interval = int(self.interval * self.ease_factor)
        else:
            self.interval = 1
            self.ease_factor = max(1.3, self.ease_factor - 0.2)

        days_since_last = (timezone.now() - self.last_answered_at).days if self.last_answered_at else 0
        time_factor = (2.718 ** (days_since_last / (self.ease_factor * self.interval)))

        difficulty = self.context.relation.difficulty.difficulty if self.context.relation.difficulty else 1.0

        # ✅ 定着度が低ければ強めに review_priority を高める
        stability_factor = 1.0 / (self.repetition_count + 1)  # 例: 1回目 1.0, 2回目 0.5, 3回目 0.33

        self.review_priority = (1 / (self.ease_factor * self.interval)) * time_factor * difficulty * stability_factor

    def schedule_next_due(self, is_correct):
        """次回復習日（next_due_at）を interval に基づいて設定"""
        days = max(1, round(self.interval)) if is_correct else 1
        self.next_due_at = timezone.now() + timedelta(days=days)
    
    def update_review_priority_by_time(self):
        days_since_last = (timezone.now() - self.last_answered_at).days if self.last_answered_at else 0
        time_factor = (2.718 ** (days_since_last / (self.ease_factor * self.interval)))
        difficulty = self.context.relation.difficulty.difficulty if self.context.relation.difficulty else 1.0

        # ✅ 定着していれば優先度を下げる方向へ
        stability_factor = 1.0 / (self.repetition_count + 1)

        self.review_priority = (1 / (self.ease_factor * self.interval)) * time_factor * difficulty * stability_factor
        self.save(update_fields=["review_priority"])


    def get_review_priority_category(self) -> str:
        """
        review_priorityに基づいて進捗色（青・黄・赤）を返す分類関数。
        """
        if self.review_priority >= 0.66:
            return 'danger'   # 赤：忘れかけ
        elif self.review_priority >= 0.33:
            return 'warning'  # 黄：そろそろ復習
        else:
            return 'stable'   # 青：定着

    @property
    def percent_accuracy(self):
        return round(self.accuracy_rate * 100, 1)

    @property
    def is_due(self) -> bool:
        """次回復習日が来ているかどうかを判定"""
        return self.next_due_at is None or timezone.now() >= self.next_due_at

    def __str__(self):
        return f"{self.student} - {self.context} (優先度: {self.review_priority:.2f})"


class QuizResult(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="quiz_results")
    context = models.ForeignKey(WordMeaningContext, on_delete=models.CASCADE, related_name="quiz_results", null=True, blank=True)
    is_correct = models.BooleanField()
    answered_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.student} - {self.context.relation.english_word.word} ({self.context.grade}年) ({'正解' if self.is_correct else '不正解'})"

    class Meta:
        ordering = ['-answered_at']
