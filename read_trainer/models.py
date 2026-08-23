from django.db import models
from accounts.models import Student

from django.utils import timezone

import math

from datetime import timedelta


class ReadingPassageQuerySet(models.QuerySet):
    def with_active_student(self):
        return self.filter(created_by__is_active=True)

    def visible_to(self, user):
        qs = self.with_active_student()  # アクティブ生徒に限定

        if not getattr(user, "is_authenticated", False):
            return qs.none()

        if getattr(user, "is_superuser", False):
            return qs

        # 不正なロールを弾く
        role = getattr(user, "role", None)
        if role not in ["organization_administrator", "classroom_administrator", "teacher", "student"]:  # 想定したロールのみ許容
            return qs.none()

        # get_role_objectの正当性についてチェック   
        if not hasattr(user, "get_role_object"):  # そもそも属性として持っていない
            return qs.none()
        try:
            role_obj = user.get_role_object()
        except Exception:
            return qs.none()
        if role_obj is None:  # ロールオブジェクトを正当に返せない
            return qs.none()

        # 以下は正当なユーザー(ロールが想定内で、role_objectも持っている)
        if role == "student":  # 自身の作成したもののみアクセス可能
            return qs.filter(created_by_id=user.id)

        if role == "teacher":
            qs = qs.filter(
                created_by__teachers=role_obj,
                created_by__organization_id=role_obj.organization_id,
            )
            return qs.distinct()

        if role == "classroom_administrator":  # 管理教室に所属している生徒のもののみアクセス可能
            return qs.filter(
                created_by__classrooms__in=role_obj.classrooms.all()
            ).distinct()

        if role == "organization_administrator":  # 自身の管理組織に所属している生徒のもののみアクセス可能
            return qs.filter(
                created_by__organization_id=role_obj.organization_id
            ).distinct()

        return qs.none()  # どれにも該当しない場合は安全側に倒して何も与えない

class ReadingPassage(models.Model):
    """
    英語長文本文と関連情報を保持するモデル
    """
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    created_by = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    token_cost = models.PositiveIntegerField(default=0)
    japanese_translation = models.TextField(blank=True)  # 和訳(新規追加)
    SOURCE_CHOICES = [
        ('textbook', '教科書準拠'),
        ('eiken', '英検対策'),
    ]
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='textbook')
    EIKEN_LEVEL_CHOICES = [
        ("5", "英検5級"),
        ("4", "英検4級"),
        ("3", "英検3級"),
        ("pre2", "英検準2級"),
        ("2", "英検2級"),
    ]

    eiken_level = models.CharField(max_length=5, choices=EIKEN_LEVEL_CHOICES, null=True, blank=True)
    objects = ReadingPassageQuerySet.as_manager()

    def __str__(self):
        return self.title or f"Reading created at {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class ReadingQuestionQuerySet(models.QuerySet):
    def with_active_student(self):
        return self.filter(passage__created_by__is_active=True)

    def visible_to(self, user):
        qs = self.with_active_student()  # アクティブ生徒に限定

        if not getattr(user, "is_authenticated", False):
            return qs.none()

        if getattr(user, "is_superuser", False):
            return qs

        # 不正なロールを弾く
        role = getattr(user, "role", None)
        if role not in ["organization_administrator", "classroom_administrator", "teacher", "student"]:  # 想定したロールのみ許容
            return qs.none()

        # get_role_objectの正当性についてチェック   
        if not hasattr(user, "get_role_object"):  # そもそも属性として持っていない
            return qs.none()
        try:
            role_obj = user.get_role_object()
        except Exception:
            return qs.none()
        if role_obj is None:  # ロールオブジェクトを正当に返せない
            return qs.none()

        # 以下は正当なユーザー(ロールが想定内で、role_objectも持っている)
        if role == "student":  # 自身の作成したもののみアクセス可能
            return qs.filter(passage__created_by_id=user.id)

        if role == "teacher":
            qs = qs.filter(
                passage__created_by__teachers=role_obj,
                passage__created_by__organization_id=role_obj.organization_id,
            )
            return qs.distinct()

        if role == "classroom_administrator":  # 管理教室に所属している生徒のもののみアクセス可能
            return qs.filter(
                passage__created_by__classrooms__in=role_obj.classrooms.all()
            ).distinct()

        if role == "organization_administrator":  # 自身の管理組織に所属している生徒のもののみアクセス可能
            return qs.filter(
                passage__created_by__organization_id=role_obj.organization_id
            ).distinct()

        return qs.none()  # どれにも該当しない場合は安全側に倒して何も与えない


class ReadingQuestion(models.Model):
    """
    英語長文に紐づく4択問題
    """
    passage = models.ForeignKey(ReadingPassage, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    option_a = models.TextField()
    option_b = models.TextField()
    option_c = models.TextField()
    option_d = models.TextField()
    correct_option = models.CharField(max_length=1, choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')])
    explanation = models.TextField()
    batch_id = models.PositiveIntegerField(default=1)
    objects = ReadingQuestionQuerySet.as_manager()

    def __str__(self):
        return f"Q: {self.question_text[:30]}..."

class ReadingAnswerQuerySet(models.QuerySet):
    def with_active_and_valid_student(self):  # 生徒がアクティブ、作成生徒がアクティブ、さらに2つの生徒が一致
        return self.filter(
            student__is_active=True,
            question__passage__created_by__is_active=True,
            question__passage__created_by=models.F("student"),
        )

    def visible_to(self, user):
        qs = self.with_active_and_valid_student()  # アクティブ生徒に限定

        if not getattr(user, "is_authenticated", False):
            return qs.none()

        if getattr(user, "is_superuser", False):
            return qs

        # 不正なロールを弾く
        role = getattr(user, "role", None)
        if role not in ["organization_administrator", "classroom_administrator", "teacher", "student"]:  # 想定したロールのみ許容
            return qs.none()

        # get_role_objectの正当性についてチェック   
        if not hasattr(user, "get_role_object"):  # そもそも属性として持っていない
            return qs.none()
        try:
            role_obj = user.get_role_object()
        except Exception:
            return qs.none()
        if role_obj is None:  # ロールオブジェクトを正当に返せない
            return qs.none()

        # 以下は正当なユーザー(ロールが想定内で、role_objectも持っている)
        if role == "student":  # 自身の作成したもののみアクセス可能
            return qs.filter(student_id=user.id)

        if role == "teacher":
            qs = qs.filter(
                student__teachers=role_obj,
                student__organization_id=role_obj.organization_id,
            )
            return qs.distinct()

        if role == "classroom_administrator":  # 管理教室に所属している生徒のもののみアクセス可能
            return qs.filter(
                student__classrooms__in=role_obj.classrooms.all()
            ).distinct()

        if role == "organization_administrator":  # 自身の管理組織に所属している生徒のもののみアクセス可能
            return qs.filter(
                student__organization_id=role_obj.organization_id
            ).distinct()

        return qs.none()  # どれにも該当しない場合は安全側に倒して何も与えない


class ReadingAnswer(models.Model):
    """
    生徒ごとの問題への解答記録
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='reading_answers')
    question = models.ForeignKey(ReadingQuestion, on_delete=models.CASCADE, related_name='answers')
    selected_option = models.CharField(max_length=1, choices=[('A','A'),('B','B'),('C','C'),('D','D')])
    is_correct = models.BooleanField()
    answered_at = models.DateTimeField(auto_now_add=True)
    objects = ReadingAnswerQuerySet.as_manager()

    def __str__(self):
        return f"{self.student} answered Q{self.question.id} ({'✔' if self.is_correct else '✘'})"


class StudentReadingPassageProgressQuerySet(models.QuerySet):
    def with_active_and_valid_student(self):  # アクティブかつ作成者と紐づいた生徒が一致しているやつのみ
        return self.filter(
            student__is_active=True,
            passage__created_by__is_active=True,
            passage__created_by=models.F("student"),
        )
    
    def visible_to(self, user):
        qs = self.with_active_and_valid_student()  # アクティブ生徒に限定

        if not getattr(user, "is_authenticated", False):
            return qs.none()

        if getattr(user, "is_superuser", False):
            return qs

        # 不正なロールを弾く
        role = getattr(user, "role", None)
        if role not in ["organization_administrator", "classroom_administrator", "teacher", "student"]:  # 想定したロールのみ許容
            return qs.none()

        # get_role_objectの正当性についてチェック   
        if not hasattr(user, "get_role_object"):  # そもそも属性として持っていない
            return qs.none()
        try:
            role_obj = user.get_role_object()
        except Exception:
            return qs.none()
        if role_obj is None:  # ロールオブジェクトを正当に返せない
            return qs.none()

        # 以下は正当なユーザー(ロールが想定内で、role_objectも持っている)
        if role == "student":  # 自身の作成したもののみアクセス可能
            return qs.filter(student_id=user.id)

        if role == "teacher":
            qs = qs.filter(
                student__teachers=role_obj,
                student__organization_id=role_obj.organization_id,
            )
            return qs.distinct()

        if role == "classroom_administrator":  # 管理教室に所属している生徒のもののみアクセス可能
            return qs.filter(
                student__classrooms__in=role_obj.classrooms.all()
            ).distinct()

        if role == "organization_administrator":  # 自身の管理組織に所属している生徒のもののみアクセス可能
            return qs.filter(
                student__organization_id=role_obj.organization_id
            ).distinct()

        return qs.none()  # どれにも該当しない場合は安全側に倒して何も与えない

class StudentReadingPassageProgress(models.Model):
    """
    生徒ごとの長文の学習進捗を記録
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    passage = models.ForeignKey(ReadingPassage, on_delete=models.CASCADE)

    # SuperMemo-2 型パラメータ
    interval = models.IntegerField(default=1)
    ease_factor = models.FloatField(default=2.5)
    repetition_count = models.IntegerField(default=0)
    next_due_at = models.DateTimeField(default=timezone.now)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    objects = StudentReadingPassageProgressQuerySet.as_manager()

    class Meta:
        unique_together = ('student', 'passage')

    def update_review_priority_by_solving(self, correct_rate: float):
        score = self._determine_sm2_score(correct_rate)
        self._update_by_sm2(score)

    def _determine_sm2_score(self, correct_rate: float) -> int:
        if correct_rate >= 0.95:
            return 5
        elif correct_rate >= 0.85:
            return 4
        elif correct_rate >= 0.70:
            return 3
        elif correct_rate >= 0.50:
            return 2
        else:
            return 1

    def _update_by_sm2(self, score: int):
        now = timezone.now()
        if score >= 3:
            self.repetition_count += 1
            if self.repetition_count == 1:
                self.interval = 1
            elif self.repetition_count == 2:
                self.interval = 6
            else:
                self.interval = int(self.interval * self.ease_factor)

            # ease_factor の調整（SuperMemo公式より）
            ef = self.ease_factor + (0.1 - (5 - score) * (0.08 + (5 - score) * 0.02))
            self.ease_factor = max(1.3, ef)
        else:
            self.repetition_count = 0
            self.interval = 1
            self.ease_factor = max(1.3, self.ease_factor - 0.2)

        self.last_reviewed_at = now
        self.next_due_at = now + timedelta(days=self.interval)
        self.save()


    def get_review_priority(self, now=None, base_lambda: float = 0.2) -> float:
        now = now or timezone.now()
        days_diff = (now - self.next_due_at).days
        return math.exp(days_diff * base_lambda) if days_diff < 0 else min(1.0, math.exp(-base_lambda * -days_diff))


    def __str__(self):
        return f"{self.student} - {self.passage} (優先度: {self.get_review_priority():.2f})"
