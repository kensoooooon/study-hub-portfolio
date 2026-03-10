# text_scheduler/models.py
"""
text_scheduler モデルの利用フロー（MVP）

このアプリは、ユーザが自分で定義した「数値で表せる学習単位」を
SM-2（SuperMemo2）方式でスケジューリングし、初回学習は任意順、
2回目以降はシステムが提示する復習日程に沿って進めることを目的とする。

■ 主要モデルの責務
- LearningMaterial:
    生徒×教材の“器”。数値レンジ（start_number..end_number）と基本方針
    （要求復習回数、1単位の想定時間、開始日・目標日、予備曜日）を保持する。
    ※ start_date/goal_date は必須。goal_date は start_date より後。

- StudentUnitProgress:
    生徒×教材×番号（整数1点）の“現在状態”を持つ。SM-2の派生値
    （ease_factor, interval_days, next_due_at, repetition_count 等）と
    集計（last_quality, total_reviews, sum_quality, total_spent_minutes 等）を保持。
    直接作成はせず、StudyLog 受理時にサーバ側で生成/更新する。

- DailyPlan:
    “今日の提案”のスナップショット。新規にやるべき件数（任意順）と、
    復習対象の番号リストを保存して提示する。時間見積もりも同時表示。

- StudyLog:
    “学習履歴の唯一の真実”。append-only（訂正は別途ログ）で、
    1回の学習イベントを記録する（initial/review, number, quality, spent_minutes など）。
    これを基に StudentUnitProgress をトランザクション内で更新する。

■ 1日の典型的な流れ
1) 教材作成（LearningMaterial）
    - 管理者/講師/本人のいずれかが対象生徒の教材を作成。
    - 数値レンジと開始日・目標日、予備曜日（例: [5,6]=土日）を設定する。

2) 今日の提案生成（DailyPlan）
    - サービス層で当日プランを計算して保存/返却。
    - 新規: 残り未学習数・残日数・1日の上限時間から件数を算出
    - 復習: StudentUnitProgress.next_due_at <= 今日 の番号を優先度順に採用
    - 予備日: 未消化があればここで吸収
    - UIには「新規は◯件（番号は任意）／復習は [135, 120, ...]」の形式で提示。

3) 学習の実施とログ（StudyLog）
    - 学習者は当日の都合で“新規番号”を自由に選んで初回学習（任意順）。
    - 終了後、StudyLog を1件ずつ投稿（number, kind, quality(0–5), spent_minutes, メモ）。
    - 投稿ごとにサーバは atomic に StudentUnitProgress を更新し、SM-2 で ease_factor/interval_days/next_due_at を再計算する。

4) 進捗の可視化（StudentUnitProgress）
    - 直近品質 last_quality、総レビュー回数 total_reviews、次回期日 next_due_at を高速に参照できる（ダッシュボード／翌日のプラン生成に利用）。

■ 設計ポリシー（要点）
- 履歴（StudyLog）と状態（StudentUnitProgress）の責務分離：
    StudyLog は改ざんしない生データ、Progress は派生キャッシュ。
    不整合時はログから全再計算できる。
- 初回学習は任意順：
    DailyPlan は“新規の件数”のみを指示し、具体的番号はユーザが選ぶ。
- 評価は品質スコア（quality: 0~5）を主軸：
    二値の正誤が必要な場面は quality>=4 を正とみなす派生指標でカバー。
- セキュリティ：
    すべての保存時に「番号が教材レンジ内」「生徒が教材の対象本人」を clean() で検証。
    StudyLog 保存→Progress 更新は同一トランザクションで実施。
"""

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

# 既存ユーザー階層（BaseUser, Student, Teacher など）を流用
from accounts.models import BaseUser, Student

from django.core.exceptions import ValidationError


class LearningMaterial(models.Model):
    """
    “教材”の器（数値レンジとポリシーを束ねる）。
    対象生徒に対して、作成者（管理者/講師/本人いずれか）と、任意で所属組織/教室を紐づけ。
    
    Attributes:
        target_student (Student): 対象となる生徒
        created_by (BaseUser): 教材の作成者
        title (CharField): 教材のタイトル
        unit_label (CharField): 学習単位(ページや例題など)
        start_number (PositiveIntegerField): 学習開始番号
        end_number (PositiveIntegerField): 学習終了番号
        required_reviews (PositiveSmallIntegerField): 要求される復習回数
        estimated_minutes_per_unit (PositiveSmallIntegerField): 1回あたりの見積もり学習時間
        start_date (DateField): 開始した日付
        goal_date (DateField): 終了予定の日付
        buffer_weekdays (JsonField): 予備曜日の指定(複数可). 0:mon ~ 6:sunのlist[int]形式を想定
        is_archived (models.BooleanField): 達成されたか否か
        created_at (教材が作成された日時)
    
    New:
        daily_minutes_budget(PositiveIntegerField): この教材に1日あたり費やせる時間(分)
    """
    target_student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="materials")
    created_by = models.ForeignKey(BaseUser, on_delete=models.PROTECT, related_name="created_materials")

    title = models.CharField(max_length=200, verbose_name="教材名")    # 例: 「体系問題集 数学1A」
    unit_label = models.CharField(max_length=32, default="番", verbose_name="学習単位", help_text="問,ページ,番など")  # 表示用: 「p」「例題」「問」「番」など

    # 学習対象レンジ（数値で表現）
    start_number = models.PositiveIntegerField(verbose_name="開始番号")     # 例: 100
    end_number   = models.PositiveIntegerField(verbose_name="終了番号")     # 例: 130

    # スケジュール方針（MVP）
    required_reviews = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(25)], verbose_name="必要復習回数")
    estimated_minutes_per_unit = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(240)],
        verbose_name="1単位あたりの推定時間",
        help_text="1単位を終えるために必要だと予測される時間(分)"
        )
    daily_minutes_budget = models.PositiveIntegerField(
        default=45, validators=[MinValueValidator(5), MaxValueValidator(600)],
        help_text="この教材に1日あたり費やせる時間(分)"
    )
    start_date = models.DateField(null=True, blank=True, verbose_name="開始日")  # 未指定なら作成日を起点
    goal_date = models.DateField(null=True, blank=True, verbose_name="終了日")   # 目標終了日（短期想定）
    buffer_weekdays = models.JSONField(default=list, blank=True, verbose_name="予備日")

    is_archived = models.BooleanField(default=False, verbose_name="達成済みか否か")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日")


    class Meta:
        constraints = [
            # NOTE:
            # 以下の CheckConstraint は設計上は正しいが、
            # 現在は既存データおよび入力フローが未整備のため一時的に無効化。
            # null/blank整理とデータマイグレーション完了後に復活予定。
            # 数字レンジ: end >= start
            # models.CheckConstraint(
            #     condition=models.Q(end_number__gte=models.F("start_number")),
            #     name="material_range_valid",
            # ),
            # 日付: start/goal は必須、かつ goal は start より後（同日不可なら __gt）
            # models.CheckConstraint(
            #     condition=(
            #         models.Q(start_date__isnull=False) &
            #         models.Q(goal_date__isnull=False) &
            #         models.Q(goal_date__gt=models.F("start_date"))
            #     ),
            #     name="material_start_and_goal_required_strict_order",
            # ),
        ]

    def clean(self):
        # buffer_weekdays: list[int in 0..6], unique
        if self.buffer_weekdays:
            if not isinstance(self.buffer_weekdays, list):
                raise ValidationError("buffer_weekdays は配列で指定してください。")
            if any((not isinstance(x, int)) or x < 0 or x > 6 for x in self.buffer_weekdays):
                raise ValidationError("buffer_weekdays は 0(mon)〜6(sun) の整数のみ許可されます。")
            if len(set(self.buffer_weekdays)) != len(self.buffer_weekdays):
                raise ValidationError("buffer_weekdays に重複があります。")

    def __str__(self):
        return f"{self.title}（{self.start_number}–{self.end_number}{self.unit_label}）"


class UnitStatus(models.TextChoices):
    NEW = "new", "new"
    LEARNING = "learning", "learning"
    REVIEWING = "reviewing", "reviewing"
    MASTERED = "mastered", "mastered"


class StudentUnitProgress(models.Model):
    """
    生徒×番号（原子単位=整数）のSM-2進捗。
    初回は任意順：number を自由に打刻すればこの行が“初回”として生成される。
    StudyLogを記録したもの(直接作成はしない)
    
    Attributes:
        student (Student): 進捗管理対象の生徒
        material (ForeignKey): 教材。教材:進捗=1:Mの想定
        number (PositiveIntegerField): 対象となったnumber(start_number <= number <= end_number)
        status = (CharField): 新規,学習中,復習中,マスターの4通りの学習状況
        
        ease_factor (FloatField): sm-2の計算に利用する指数
        interval_days (PositiveIntegerField): 直近の間隔
        next_due_at (DateTimeField): 次の学習日時
        repetition_count (PositiveIntegerField): 何回学習したか
        
        last_studied_at (DateTimeField): 最後の学習日
        total_spent_minutes (PositiveIntegerField): 費やされた時間
        
        last_quality (PositiveSmallIntegerField): 最後に学習した際の自己評価(0~5)
        total_reviews (PositiveIntegerField): 合計の復習回数
        sum_quality (PositiveIntegerField): 合計の自己評価

    Developing:
        二値系の評価は排除
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="text_sched_progress")
    material = models.ForeignKey(LearningMaterial, on_delete=models.CASCADE, related_name="unit_progress")
    number = models.PositiveIntegerField()  # 例: 135

    # 状態とSM-2系
    status = models.CharField(
        max_length=12,
        choices=UnitStatus.choices,
        default=UnitStatus.NEW,
    )
    ease_factor = models.FloatField(default=2.5)
    interval_days = models.PositiveIntegerField(default=0)  # 直近の間隔（日）
    next_due_at = models.DateTimeField(null=True, blank=True)
    repetition_count = models.PositiveIntegerField(default=0)

    # 実績集計（サマリ）
    last_studied_at = models.DateTimeField(null=True, blank=True)
    total_spent_minutes = models.PositiveIntegerField(default=0)
    
    # 評価用
    last_quality = models.PositiveSmallIntegerField(null=True, blank=True)
    total_reviews = models.PositiveIntegerField(default=0)
    sum_quality = models.PositiveIntegerField(default=0)


    class Meta:
        unique_together = ("student", "material", "number")
        indexes = [
            models.Index(fields=["student", "material", "number"]),
            models.Index(fields=["student", "material", "next_due_at"]),
        ]
        
    def clean(self):
        if not(self.material.start_number <= self.number <= self.material.end_number):
            raise ValidationError("numberが教材の範囲外です。")
        if self.student_id != self.material.target_student_id:
            raise ValidationError("studentとtarget_studentが一致しません。")

    def __str__(self):
        return f"{self.student} / {self.material.title} #{self.number}"


class DailyPlan(models.Model):
    """
    “当日の提案セット”のスナップショット（MVP）。
    初回と復習の件数・リストを保存しておき、UIに提示する。
    
    Attributes:
        student (Student): 対象となる生徒
        material (LearningMaterial): 対象となる教材
        date (DateField): 学習の日程
        
        suggested_new_count (PositiveSmallIntegerField): 新規に学習すべき教材の件数
        suggested_review_numbers (JsonField): 推奨される復習教材の番号
        estimated_total_minutes (PositiveIntegerField): 予想される学習時間の合計
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="text_sched_daily_plans")
    material = models.ForeignKey(LearningMaterial, on_delete=models.CASCADE, related_name="daily_plans")
    date = models.DateField()

    suggested_new_count = models.PositiveSmallIntegerField(default=0)
    suggested_review_numbers = models.JSONField(default=list, blank=True)  # [135, 120, 101] 等
    estimated_total_minutes = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("student", "material", "date")

    def clean(self):
        nums = self.suggested_review_numbers or []
        if any((not isinstance(x, int)) for x in nums):
            raise ValidationError("suggested_review_numbers は整数配列で指定してください。")
        start, end = self.material.start_number, self.material.end_number
        if any(x < start or x > end for x in nums):
            raise ValidationError("suggested_review_numbers に教材範囲外の番号が含まれています。")

    def __str__(self):
        return f"{self.date} {self.student} {self.material.title}"


class StudyLog(models.Model):
    """
    学習実績の唯一の真実。これに基づいてProgressを更新する。
    append-onlyのみ(修正は別途追加)
    
    Attributes:
        student(Student): 対象生徒
        material(LearningMaterial): 対象教材
        number (PositiveIntegerField): 学習した番号
        kind (CharField): initial(初期) or review(復習)
        
        quality (PositiveSmallIntegerField): 理解度の自己評価
        point_1, point_2, point_3 (CharField): 一言メモ
        
        is_correct (BooleanField): 正しいか否か？？
    """
    KIND_CHOICES = [
        ("initial", "初回学習"),
        ("review", "復習"),
    ]
    kind = models.CharField(max_length=7, choices=KIND_CHOICES)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="text_sched_logs")
    material = models.ForeignKey(LearningMaterial, on_delete=models.CASCADE, related_name="logs")
    number = models.PositiveIntegerField()  # 学習した番号
    studied_at = models.DateTimeField(default=timezone.now)
    # 質(自己評価)
    quality = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        null=True, blank=True
    )  # SM-2準拠 (0–5)。UIは☆1–☆5→内部4..0等にマッピングしてもOK
    point_1 = models.CharField(max_length=300, blank=True, default="")
    point_2 = models.CharField(max_length=300, blank=True, default="")
    point_3 = models.CharField(max_length=300, blank=True, default="")

    IS_CORRECT_CHOICES = [
        ("true", "正解"),
        ("false", "不正解"),
        ("unknown", "不明"),
    ]
    is_correct = models.CharField(max_length=10, choices=IS_CORRECT_CHOICES, default="unknown")
    spent_minutes = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(240)], default=0
    )

    source = models.CharField(max_length=16, default="ui")  # 将来 line 等

    class Meta:
        ordering = ["-studied_at", "-id"]
        indexes = [
            models.Index(fields=["student", "material", "number"]),
            models.Index(fields=["student", "material", "studied_at"]),
        ]
        constraints = [
            # qualityは0以上5以下
            models.CheckConstraint(
                condition=models.Q(quality__gte=0, quality__lte=5) | models.Q(quality__isnull=True),
                name="log_quality_range_0_5_or_null",
            ),
            # 費やされた時間は0分以上240分以下
            models.CheckConstraint(
                condition=models.Q(spent_minutes__gte=0, spent_minutes__lte=240),
                name="log_spent_minutes_0_240",
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=["initial", "review"]),
                name="log_kind_valid",
            ),
        ]

    def clean(self):
        # 必須関係
        if self.student_id is None or self.material_id is None:
            raise ValidationError("student / material が未設定です。")
        if self.number is None:
            raise ValidationError("number は必須です。")

        # 教材レンジの存在確認（古いデータ対策）
        start = getattr(self.material, "start_number", None)
        end = getattr(self.material, "end_number", None)
        if start is None or end is None:
            raise ValidationError("教材の開始番号/終了番号が未設定です。教材を編集して設定してください。")

        # 範囲チェック
        if not (start <= self.number <= end):
            raise ValidationError(f"number が教材の範囲外です（{start}〜{end}）。")

        # student と material の整合
        if self.student_id != self.material.target_student_id:
            raise ValidationError("student と material.target_student が一致しません。")

    def __str__(self):
        return f"{self.studied_at:%Y-%m-%d %H:%M} {self.student} {self.material.title} #{self.number} ({self.kind})"
