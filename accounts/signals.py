"""
accounts関連のデータが変更された際にシグナルを受信し、データの整合性をチェックするためのファイル

11/16
    新規作成
    validate_student_classroomsを追加
        student.organizationを正としたうえで、所属している教室の組織が一致しているかをチェック
        「自分が所属している組織はαなのに、所属している教室の所属教室はβである」という矛盾を防止する

issue #140
    validate_student_teachersを追加
        Student.teachers（Student側がオーナーのM2M）にはm2m_changedによる組織整合性チェックが
        存在しておらず、フォームを経由しない書き込み経路（Django Admin、management command等）で
        異なる組織の講師が検知されずに紐付いてしまう非対称な保護構造だったため追加した。
        student.teachers.add(...)（順方向）・teacher.students.add(...)（逆方向）の
        どちらから呼び出された場合も検証する。
    既存3レシーバーの `if action not in ("pre_add", "pre_set"): return` を整理
        Django（本プロジェクトはDjango 5.1.3）のm2m_changedが送出するactionに
        "pre_set" という値は存在しない（.set()は内部でremove()+add()に分解されるため、
        新規追加分は必ずpre_addで発火する）。挙動を変えないデッドコード整理。
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
    # 追加時だけ見る（削除やclearは対象外）
    if action != "pre_add":
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


@receiver(m2m_changed, sender=Student.teachers.through)
def validate_student_teachers(sender, instance, action, reverse, pk_set, **kwargs):
    """
    Student.teachers の ManyToMany 関係が変更されるときに、
    生徒の所属 organization と講師の organization が一致しているかを検証する。
    student.teachers.add(...)（順方向）・teacher.students.add(...)（逆方向）の
    どちらから呼び出された場合も検証する。
    """
    # 追加時だけ見る（削除やclearは対象外）
    if action != "pre_add":
        return

    if reverse:
        # instance は Teacher、pk_set は追加しようとしている Student の pk 集合
        invalid = Student.objects.filter(pk__in=pk_set).exclude(
            organization_id=instance.organization_id
        )
        if invalid.exists():
            # ここで止める＝講師への追加自体がロールバックされる
            raise ValidationError(
                f"講師の所属組織({instance.organization})と異なる組織の生徒が含まれています。"
            )
    else:
        # instance は Student、pk_set は追加しようとしている Teacher の pk 集合
        invalid = Teacher.objects.filter(pk__in=pk_set).exclude(
            organization_id=instance.organization_id
        )
        if invalid.exists():
            # ここで止める＝講師への追加自体がロールバックされる
            raise ValidationError(
                f"生徒の所属組織({instance.organization})と異なる組織の講師が含まれています。"
            )


@receiver(m2m_changed, sender=Teacher.classrooms.through)
def validate_teacher_classrooms(sender, instance, action, pk_set, **kwargs):
    """
    Teacher.classrooms の ManyToMany 関係が変更されるときに、
    教師の所属 organization と教室の organization が一致しているかを検証する。
    """
    # 追加時だけ見る（削除やclearは対象外）
    if action != "pre_add":
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
    # 追加時だけ見る（削除やclearは対象外）
    if action != "pre_add":
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