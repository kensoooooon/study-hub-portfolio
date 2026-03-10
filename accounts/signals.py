"""
accounts関連のデータが変更された際にシグナルを受信し、データの整合性をチェックするためのファイル

11/16
    新規作成
    validate_student_classroomsを追加
        student.organizationを正としたうえで、所属している教室の組織が一致しているかをチェック
        「自分が所属している組織はαなのに、所属している教室の所属教室はβである」という矛盾を防止する
"""

from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.core.exceptions import ValidationError

from accounts.models import Student, Teacher, ClassroomAdministrator, Classroom


@receiver(m2m_changed, sender=Student.classrooms.through)
def validate_student_classrooms(sender, instance, action, pk_set, **kwargs):
    """
    Student.classrooms の ManyToMany 関係が変更されるときに、
    生徒の所属 organization と教室の organization が一致しているかを検証する。
    """
    # 追加/差し替え時だけ見る（削除やclearは対象外）
    if action not in ("pre_add", "pre_set"):
        return

    # まだ organization が決まっていない／移行中の場合はスキップ（方針に応じて調整可）
    if not instance.organization_id:
        return

    # これから紐付けようとしている教室
    invalid = Classroom.objects.filter(pk__in=pk_set).exclude(
        organization_id=instance.organization_id
    )

    if invalid.exists():
        # ここで止める＝教室への追加自体がロールバックされる
        raise ValidationError(
            f"生徒の所属組織({instance.organization})と異なる組織の教室が含まれています。"
        )

@receiver(m2m_changed, sender=Teacher.classrooms.through)
def validate_teacher_classrooms(sender, instance, action, pk_set, **kwargs):
    """
    Teacher.classrooms の ManyToMany 関係が変更されるときに、
    教師の所属 organization と教室の organization が一致しているかを検証する。
    """
    # 追加/差し替え時だけ見る（削除やclearは対象外）
    if action not in ("pre_add", "pre_set"):
        return

    # まだ organization が決まっていない／移行中の場合はスキップ（方針に応じて調整可）
    if not instance.organization_id:
        return

    # これから紐付けようとしている教室のうち、所属組織の矛盾が発生するもの
    invalid = Classroom.objects.filter(pk__in=pk_set).exclude(
        organization_id=instance.organization_id
    )

    if invalid.exists():
        # ここで止める＝教室への追加自体がロールバックされる
        raise ValidationError(
            f"教師の所属組織({instance.organization})と異なる組織の教室が含まれています。"
        )


@receiver(m2m_changed, sender=ClassroomAdministrator.classrooms.through)
def validate_classroom_administrator_classrooms(sender, instance, action, pk_set, **kwargs):
    """
    ClassroomAdministrator.classrooms の ManyToMany 関係が変更されるときに、
    教室管理者の所属 organization と教室の organization が一致しているかを検証する。
    """
    # 追加/差し替え時だけ見る（削除やclearは対象外）
    if action not in ("pre_add", "pre_set"):
        return

    # まだ organization が決まっていない／移行中の場合はスキップ（方針に応じて調整可）
    if not instance.organization_id:
        return

    # これから紐付けようとしている教室のうち、所属組織の矛盾が発生するもの
    invalid = Classroom.objects.filter(pk__in=pk_set).exclude(
        organization_id=instance.organization_id
    )

    if invalid.exists():
        # ここで止める＝教室への追加自体がロールバックされる
        raise ValidationError(
            f"教室管理者の所属組織({instance.organization})と異なる組織の教室が含まれています。"
        )