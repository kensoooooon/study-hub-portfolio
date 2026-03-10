# text_scheduler/services/progress.py
from __future__ import annotations
from dataclasses import dataclass
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError



from text_scheduler.models import (
    LearningMaterial, StudyLog, StudentUnitProgress, UnitStatus
)

MIN_EF = 1.3

def _sm2_next(ease_factor: float, interval_days: int, repetition: int, quality: int):
    # EF' の更新式（SuperMemo2）
    ef_prime = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ef_prime = max(MIN_EF, ef_prime)

    if quality < 3:
        # 失敗：反復をリセット
        return ef_prime, 1, 1
    else:
        if repetition <= 1:
            next_interval = 1 if repetition == 0 else 6
        else:
            next_interval = round(interval_days * ef_prime)
        return ef_prime, next_interval, repetition + 1

@transaction.atomic
def apply_study_log(log: StudyLog) -> StudentUnitProgress:
    material = log.material
    student = log.student

    # サニティチェック：レンジ/本人一致
    if not (material.start_number <= log.number <= material.end_number):
        raise ValidationError("numberが教材レンジ外です。")
    if student.id != material.target_student_id:
        raise ValidationError("studentとtarget_studentが一致しません。")

    # 進捗レコードを取得/作成
    sup, _ = StudentUnitProgress.objects.select_for_update().get_or_create(
        student=student, material=material, number=log.number,
        defaults={}
    )

    # 既存値を取り出し
    ef = sup.ease_factor
    interval = sup.interval_days
    rep = sup.repetition_count
    q = int(log.quality) if log.quality is not None else 3  # 未指定は中立扱い

    # 次回計算
    ef2, next_interval, next_rep = _sm2_next(ef, interval, rep, q)

    sup.ease_factor = ef2
    sup.interval_days = next_interval if q >= 3 else 1
    sup.repetition_count = next_rep if q >= 3 else 1
    sup.next_due_at = timezone.now() + timedelta(days=sup.interval_days)
    sup.last_studied_at = log.studied_at
    sup.total_spent_minutes = (sup.total_spent_minutes or 0) + (log.spent_minutes or 0)
    sup.last_quality = q
    sup.total_reviews = (sup.total_reviews or 0) + 1
    sup.sum_quality = (sup.sum_quality or 0) + q
    # ▼ 状態遷移（簡易ルール）
    required = int(material.required_reviews or 0)
    if sup.repetition_count <= 1:
        sup.status = UnitStatus.LEARNING
    elif required and sup.repetition_count >= required:
        sup.status = UnitStatus.MASTERED
    else:
        sup.status = UnitStatus.REVIEWING


    sup.full_clean()
    sup.save()
    return sup
