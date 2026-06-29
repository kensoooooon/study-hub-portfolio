from accounts.models import (
    Student,
    Teacher,
    ClassroomAdministrator,
)


def check_org_classroom_integrity():
    print("=== ClassroomAdministrator × Classroom の矛盾チェック ===")
    cas_with_classrooms = (
        ClassroomAdministrator.objects
        .filter(classrooms__isnull=False)
        .select_related("organization")
        .prefetch_related("classrooms__organization")
        .distinct()
    )

    for ca in cas_with_classrooms:
        bad_cls = [
            cl for cl in ca.classrooms.all()
            if cl.organization_id != ca.organization_id
        ]
        if not bad_cls:
            continue

        print(f"- CA: {ca} (org={ca.organization})")
        for cl in bad_cls:
            print(f"    * 教室: {cl} (org={cl.organization})  ← 組織不一致")

    print("\n=== Teacher × Classroom の矛盾チェック ===")
    teachers_with_classrooms = (
        Teacher.objects
        .filter(classrooms__isnull=False)
        .select_related("organization")
        .prefetch_related("classrooms__organization")
        .distinct()
        )

    for t in teachers_with_classrooms:
        bad_cls = [
            classroom for classroom in t.classrooms.all()
            if classroom.organization_id != t.organization_id
        ]
        if not bad_cls:
            continue

        print(f"- Teacher: {t} (org={t.organization})")
        for cl in bad_cls:
            print(f"    * 教室: {cl} (org={cl.organization})  ← 組織不一致")

    print("\n=== Student × Classroom の矛盾チェック ===")
    students_with_classrooms = (
        Student.objects
        .filter(classrooms__isnull=False)
        .select_related("organization")
        .prefetch_related("classrooms__organization")
        .distinct()
        )

    for s in students_with_classrooms:
        bad_cls = [
            classroom for classroom in s.classrooms.all()
            if classroom.organization_id != s.organization_id
        ]
        if not bad_cls:
            continue

        print(f"- Student: {s} (org={s.organization})")
        for cl in bad_cls:
            print(f"    * 教室: {cl} (org={cl.organization})  ← 組織不一致")

    print("\n=== Student × Teacher の矛盾チェック ===")
    students_with_teachers = (
        Student.objects
        .filter(teachers__isnull=False)
        .select_related("organization")
        .prefetch_related("teachers__organization")
        .distinct()
        )

    for s in students_with_teachers:
        bad_teachers = [
            t for t in s.teachers.all()
            if s.organization_id != t.organization_id
        ]
        if not bad_teachers:
            continue

        print(f"- Student: {s} (org={s.organization})")
        for t in bad_teachers:
            print(f"    * Teacher: {t} (org={t.organization})  ← 組織不一致")


    print("\n=== チェック完了 ===")
