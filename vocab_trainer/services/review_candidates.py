"""
期限を考慮した復習候補の取得を行う関数
"""
from django.utils import timezone

from accounts.models import Student
from vocab_trainer.models import StudentContextProgress


def get_review_candidates_by_due(student: Student, max_candidates: int | None = None) -> list[StudentContextProgress]:
    """
    next_due_atを加味して復習候補を返す（件数制限は任意）

    Args:
        student(Student): 対象となる生徒
        max_candidates (int | None): 候補の最大数
        
    Returns:
        (list[StudentContextProgress]): 条件を満たすStudentContextProgress
    """
    # 生徒が一致、教科書が一致、既に復習タイミングが来ているものを全件取得
    due_candidates = StudentContextProgress.objects.filter(
        student=student,
        context__chapter__textbook=student.textbook,
        next_due_at__lte=timezone.now()
    ).select_related(
    "context",
    "context__relation",
    "context__relation__english_word",
    "context__relation__japanese_meaning",
    "context__chapter",
    ).order_by('-review_priority')

    if max_candidates is not None and due_candidates.count() >= max_candidates:
        return list(due_candidates[:max_candidates])

    # フォールバックの追加
    fallback_needed = (max_candidates - due_candidates.count()) if max_candidates else None
    fallback = StudentContextProgress.objects.filter(
        student=student,
        context__chapter__textbook=student.textbook
    ).exclude(id__in=due_candidates.values_list('id', flat=True)).order_by('-review_priority')

    if fallback_needed:
        fallback = fallback[:fallback_needed]

    return list(due_candidates) + list(fallback)