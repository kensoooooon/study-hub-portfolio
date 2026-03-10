"""
@startuml
title Django Model UML for Math Trainer
class ProblemType {
  name: CharField
  grade: IntegerField
}
class ProblemSession {
  id: UUIDField
  student: ForeignKey(Student)
  problem_type: ForeignKey(ProblemType)
  created_at: DateTimeField
  mode: CharField
  score: FloatField
}
class ProblemInstance {
  session: ForeignKey(ProblemSession)
  problem_type: ForeignKey(ProblemType)
  question_text: TextField
  answer_text: CharField
  choice_texts: JSONField
  created_at: DateTimeField
}
class StudentAnswer {
  problem_instance: ForeignKey(ProblemInstance)
  student: ForeignKey(Student)
  selected_choice: CharField
  is_correct: BooleanField
  answered_at: DateTimeField
}
class StudentProblemProgress {
  student: ForeignKey(Student)
  problem_type: ForeignKey(ProblemType)
  total_attempt: PositiveIntegerField
  correct_count: PositiveIntegerField
  repetition_count: PositiveIntegerField
  interval: PositiveIntegerField
  ease_factor: FloatField
  next_due_at: DateField
}
ProblemSession --> Student
ProblemSession --> ProblemType
ProblemInstance --> ProblemSession
ProblemInstance --> ProblemType
StudentAnswer --> ProblemInstance
StudentAnswer --> Student
StudentProblemProgress --> Student
StudentProblemProgress --> ProblemType
@enduml

ProblemType
    問題のタイプを規定する（学年×問題タイプ）(eg. 小学2年生×時計)
    一応、文部科学省の指導要領をに基づく

ProblemInstance
    問題の最小構成要素(1問の規定)
    正解と選択肢などの出題と採点に必要な要素を保持する
    ProblemSession: ProblemInstance = 1: Mとなっており、1回のセッションは複数のインスタンスから構成されることを意図している

ProblemSession
    1セットの問題構成要素の規定
    ProblemSession: ProblemInstance = 1: M
    その場での採点、および後から講師が入力することを想定
    
StudentAnswer
    特定の問題インスタンスに対する生徒の解答を記録
    復習等での利用を想定

StudentProblemProgress
    問題タイプを基準とした進捗の管理
    sm-2型の復習管理を前提としている
"""
from django.db import models
import uuid
from django.db.models import UniqueConstraint

from accounts.models import Student, BaseUser

from accounts.models.user_models import GradeChoices


class ProblemType(models.Model):
    """問題タイプ（例: 小数の計算、連立方程式など）

    Attributes:
        name (str): 問題タイプ名（例: 時計, 単位変換）
        grade (int): 対象となる学年
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="問題タイプ名")
    grade = models.IntegerField(
        choices=GradeChoices.choices[:13],
        null=True, blank=True,
        verbose_name="対象学年"
    )

    class Meta:
        constraints = [
            UniqueConstraint(fields=['name', 'grade'], name='unique_problemtype_name_grade')
        ]


    def __str__(self):
        return f"{self.get_grade_display()} - {self.name}"


class ProblemSessionQuerySet(models.QuerySet):
    def visible_to(self, user):
        qs = self  # ← 受け取った self を活かす（ここが重要）

        if not getattr(user, "is_authenticated", False):
            return qs.none()
        if getattr(user, "is_superuser", False):
            return qs

        role = getattr(user, "role", None)
        if role == "student":
            return qs.filter(student_id=user.id)

        role_obj = user.get_role_object() if hasattr(user, "get_role_object") else None
        if role == "teacher" and role_obj:
            return qs.filter(student__in=role_obj.get_students())
        if role == "classroom_administrator" and role_obj:
            return qs.filter(student__classrooms__in=role_obj.classrooms.all()).distinct()
        if role == "organization_administrator" and role_obj:
            return qs.filter(student__classrooms__organization__in=role_obj.organizations.all()).distinct()

        return qs.none()



class ProblemSession(models.Model):
    """1回の出題セッション（表示・印刷共通）

    Attributes:
        id (UUID): セッション識別子（プリントや演習で利用）
        student (Student): このセッションを持つ生徒
        problem_type (ProblemType): 出題された問題のタイプ
        created_at (datetime): セッションが作成された日時
        mode (str): 出題形式（'display' または 'print'）
        score (float): 採点結果（教師入力など、任意)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    problem_type = models.ForeignKey(ProblemType, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    mode = models.CharField(max_length=20, choices=[("display", "Display"), ("print", "Print")])
    score = models.FloatField(null=True, blank=True)
    objects = ProblemSessionQuerySet.as_manager()

    def can_be_accessed_by(self, user) -> bool:
        """
        対象セッションが特定ユーザーからアクセス可能か
        
        Args:
            user (Student | Teacher | ClassroomAdministrator | OrganizationAdministrator): 対象となるユーザー
        
        Returns:
            (bool): アクセス可能ならTrue,そうでないならFalse
            
        Notes:
            getattr()を繰り返し用いることで、動作の停止ではなくFalseで返すことを重視
        """
        # 未ログイン
        if not getattr(user, "is_authenticated", False):
            return False
        # スーパーユーザー
        if getattr(user, "is_superuser", False):
            return True

        # 生徒本人は自分のセッションのみ（FKの生値で比較＝追加SELECTなし）
        if getattr(user, "role", None) == "student":
            return self.student_id == user.id

        # 役割オブジェクトに委譲（Teacher / ClassroomAdmin / OrgAdmin）
        get_obj = getattr(user, "get_role_object", None)
        role_obj = get_obj() if callable(get_obj) else None
        if not role_obj or not hasattr(role_obj, "can_manage_student"):
            return False

        try:
            return bool(role_obj.can_manage_student(self.student))
        except Exception:
            return False

    def __str__(self):
        return f"{self.student.username} - {self.problem_type.name} - {self.mode} @ {self.created_at:%Y-%m-%d}"



class ProblemInstance(models.Model):
    """出題された問題1件の情報（内容＋正解など）

    Attributes:
        session (ProblemSession): 所属するセッション
        problem_type (ProblemType): 問題のタイプ
        question_text (str): 出題された問題文
        answer_text (str): 正解の文字列
        choice_texts (list[str]): 選択肢（answerを含む）
        created_at (datetime): この問題インスタンスの作成日時
        metadata (JSONFiled): 描画などの補足情報
        order (int): 出題した順番
        correct_index (int): 正しい選択番号
    
    Developing:
        correct_indexは将来的な構造変更(MCQなどの抽象クラスの導入による抽象化)に備えた機構
        現システムでは利用していない
    """
    session = models.ForeignKey(ProblemSession, on_delete=models.CASCADE, related_name="problems")
    problem_type = models.ForeignKey(ProblemType, on_delete=models.CASCADE)

    question_text = models.TextField()
    answer_text = models.CharField(max_length=200)
    choice_texts = models.JSONField(help_text="選択肢のリスト（answerを含む）")

    created_at = models.DateTimeField(auto_now_add=True)

    metadata = models.JSONField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)
    correct_index = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["session", "order", "id"]  # 念のため安定化

    def __str__(self):
        return f"{self.problem_type.name}: {self.question_text[:20]}"
    

class StudentAnswer(models.Model):
    """生徒の実際の選択と正誤

    Attributes:
        problem_instance (ProblemInstance): 該当の問題インスタンス
        student (Student): 解答者
        selected_choice (str): 生徒が選んだ選択肢
        is_correct (bool): 正答かどうか
        answered_at (datetime): 解答日時
    
    Developing:
        selected_choice is blank=True
            プリント型の出題は後ほど採点することを前提としているため、いったん空欄を許容する。
            nullにすると扱いがぶれるため、blankで文字列を統一する
    """
    problem_instance = models.ForeignKey(ProblemInstance, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    selected_choice = models.CharField(max_length=200, blank=True, default="")
    is_correct = models.BooleanField()
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'problem_instance'],
                name='uniq_student_problem_instance'
            )
        ]


class StudentProblemProgress(models.Model):
    """生徒ごとの問題種別に対する進捗モデル。
    正答数・解答回数、SM-2のパラメータなどを含む。

    Attributes:
        student (Student): 対象生徒
        problem_type (ProblemType): 対象問題タイプ
        total_attempt (int): 試行回数
        correct_count (int): 正答数
        repetition_count (int): SM-2: 反復回数
        interval (int): SM-2: 次の間隔（日数）
        ease_factor (float): SM-2: 難易度係数
        next_due_at (date): 次回復習予定日"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    problem_type = models.ForeignKey(ProblemType, on_delete=models.CASCADE)

    total_attempt = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)

    # SM-2に必要なパラメータ
    repetition_count = models.PositiveIntegerField(default=0)
    interval = models.PositiveIntegerField(default=1)  # 次回までの日数
    ease_factor = models.FloatField(default=2.5)
    next_due_at = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ('student', 'problem_type')

    @property
    def accuracy(self):
        """正答率を計算（テンプレートや表示用）"""
        return self.correct_count / self.total_attempt if self.total_attempt else 0.0

    def __str__(self):
        return f"{self.student.username} - {self.problem_type.name} ({self.accuracy:.1%})"
