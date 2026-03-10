import pytest
from django.urls import reverse
from django.utils import timezone
from text_scheduler.models import StudentUnitProgress, StudyLog
from services import apply_study_log


@pytest.mark.django_db
def test_due_is_removed_after_review(client, student, material):
    # 例: number=145 の due 状態を作る（StudentUnitProgress を直接セットでも可）
    sup = StudentUnitProgress.objects.create(
        student=student, material=material, number=145,
        next_due_at=timezone.now() - timezone.timedelta(days=1),
        repetition_count=1,
    )

    # 一覧（初回）→ 145 が表示される想定
    resp1 = client.get(reverse("text_scheduler:material_list") + f"?student_id={student.id}")
    assert "145" in resp1.content.decode()

    # 復習を登録
    log = StudyLog.objects.create(student=student, material=material, number=145, kind="review", quality=4)
    apply_study_log(log)

    # 一覧（再アクセス）→ 145 が消えている
    resp2 = client.get(reverse("text_scheduler:material_list") + f"?student_id={student.id}")
    assert "145" not in resp2.content.decode()
