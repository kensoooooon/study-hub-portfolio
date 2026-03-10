from django.db.models import F, Q
from accounts.models import (
    Organization,
    Classroom,
    Student,
    Teacher,
    ClassroomAdministrator,
    OrganizationAdministrator,
)


def check_org_classroom_integrity():
    print("=== ClassroomAdministrator × Classroom の矛盾チェック ===")
    # 組織はあるが、紐付いている教室の organization が一致しない
    ca_conflicts = ClassroomAdministrator.objects.filter(
        organization__isnull=False,
        classrooms__isnull=False,
    ).exclude(
        classrooms__organization=F("organization")
    ).distinct()

    for ca in ca_conflicts:
        print(f"- CA: {ca} (org={ca.organization})")
        bad_cls = ca.classrooms.exclude(organization=ca.organization)
        for cl in bad_cls:
            print(f"    * 教室: {cl} (org={cl.organization})  ← 組織不一致")

    # organization が None なのに classrooms が付いている
    ca_org_null_with_classrooms = ClassroomAdministrator.objects.filter(
        organization__isnull=True,
        classrooms__isnull=False,
    ).distinct()
    if ca_org_null_with_classrooms.exists():
        print("\n[警告] organization=None なのに classrooms を持つ教室管理者:")
        for ca in ca_org_null_with_classrooms:
            print(f"- CA: {ca} (org=None) classrooms={[c.name for c in ca.classrooms.all()]}")
    else:
        print("\norganization=None で classrooms を持つ教室管理者はいません。")

    print("\n=== Teacher × Classroom の矛盾チェック ===")
    teacher_conflicts = Teacher.objects.filter(
        organization__isnull=False,
        classrooms__isnull=False,
    ).exclude(
        classrooms__organization=F("organization")
    ).distinct()

    for t in teacher_conflicts:
        print(f"- Teacher: {t} (org={t.organization})")
        bad_cls = t.classrooms.exclude(organization=t.organization)
        for cl in bad_cls:
            print(f"    * 教室: {cl} (org={cl.organization})  ← 組織不一致")

    teacher_org_null_with_classrooms = Teacher.objects.filter(
        organization__isnull=True,
        classrooms__isnull=False,
    ).distinct()
    if teacher_org_null_with_classrooms.exists():
        print("\n[警告] organization=None なのに classrooms を持つ講師:")
        for t in teacher_org_null_with_classrooms:
            print(f"- Teacher: {t} (org=None) classrooms={[c.name for c in t.classrooms.all()]}")
    else:
        print("\norganization=None で classrooms を持つ講師はいません。")

    print("\n=== Student × Classroom の矛盾チェック ===")
    student_classroom_conflicts = Student.objects.filter(
        organization__isnull=False,
        classrooms__isnull=False,
    ).exclude(
        classrooms__organization=F("organization")
    ).distinct()

    for s in student_classroom_conflicts:
        print(f"- Student: {s} (org={s.organization})")
        bad_cls = s.classrooms.exclude(organization=s.organization)
        for cl in bad_cls:
            print(f"    * 教室: {cl} (org={cl.organization})  ← 組織不一致")

    print("\n=== Student × Teacher の矛盾チェック ===")
    # 生徒とteacherの organization が異なる（teacher.organization が None のケースは別扱い）
    student_teacher_conflicts = Student.objects.filter(
        organization__isnull=False,
        teachers__organization__isnull=False,
    ).exclude(
        teachers__organization=F("organization")
    ).distinct()

    for s in student_teacher_conflicts:
        print(f"- Student: {s} (org={s.organization})")
        bad_teachers = s.teachers.exclude(organization=s.organization).exclude(organization__isnull=True)
        for t in bad_teachers:
            print(f"    * Teacher: {t} (org={t.organization})  ← 組織不一致")

    # teacher.organization が None で紐付いているケース（移行中の暫定データとして一覧）
    student_with_null_org_teachers = Student.objects.filter(
        teachers__organization__isnull=True
    ).distinct()
    if student_with_null_org_teachers.exists():
        print("\n[注意] organization=None の講師が紐付いている生徒（移行途中想定）:")
        for s in student_with_null_org_teachers:
            null_org_teachers = s.teachers.filter(organization__isnull=True)
            print(f"- Student: {s} (org={s.organization})")
            for t in null_org_teachers:
                print(f"    * Teacher: {t} (org=None)")
    else:
        print("\norganization=None の講師が紐付いている生徒はいません。")

    print("\n=== チェック完了 ===")
