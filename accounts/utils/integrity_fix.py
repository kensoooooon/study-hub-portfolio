"""
既存データを組織の壁を確立した状況でも使えるようにするためのメソッド

方針
・データ本体に紐づけられた組織が最優先
    データ本体と異なる組織は採用しない
    紐づけられた組織がなく、なおかつ他の紐づいたデータには1件組織が紐づいている
    →組織を紐づけ

・講師が組織外の生徒を担当している場合は、修正せずに警告を出す(どちらが正しいか判断する要素がないため)


・実際の運用は、以下のようにshellで行う
from accounts.utils.integrity_fix import fix_org_classroom_integrity

# まずは dry_run=True で内容確認
res = fix_org_classroom_integrity(dry_run=True)
for c in res["changes"]:
    print("[CHANGE]", c)
for w in res["warnings"]:
    print("[WARN ]", w)

# 問題なさそうなら本番適用
res_real = fix_org_classroom_integrity(dry_run=False)

for c in res["changes"]:
    print("[CHANGE]", c)
for w in res["warnings"]:
    print("[WARN ]", w)
"""

from django.db import transaction
from typing import Dict, Any

from accounts.models import (
    Classroom,
    Student,
    Teacher,
    ClassroomAdministrator,
)


@transaction.atomic
def fix_org_classroom_integrity(dry_run: bool = True) -> Dict[str, Any]:
    """
    組織・教室・ユーザー（生徒/講師/教室管理者）の整合性を
    可能な範囲で自動修正する。

    dry_run=True の場合は DB を変更せず、変更予定内容だけを返す。
    """
    result: Dict[str, Any] = {
        "changes": [],
        "warnings": [],
    }

    # --- ClassroomAdministrator の不正教室の切り離し ---
    for ca in ClassroomAdministrator.objects.all():
        classrooms = ca.classrooms.all()

        # org があるのに、別組織の教室をぶら下げている場合 → その教室だけ外す
        if ca.organization:
            invalid_cls = classrooms.exclude(organization=ca.organization)
            if invalid_cls.exists():
                msg = (
                    f"[CA] {ca} : 異なる組織の教室を切り離し -> "
                    f"{[c.name for c in invalid_cls]}"
                )
                result["changes"].append(msg)
                if not dry_run:
                    ca.classrooms.remove(*invalid_cls)

    # --- Teacher の不正教室の切り離し ---
    for teacher in Teacher.objects.all():
        t_classrooms = teacher.classrooms.all()
        t_students = teacher.students.all()

        # org があるのに、別組織の教室をぶら下げている場合 → その教室だけ外す
        if teacher.organization:
            invalid_cls = t_classrooms.exclude(organization=teacher.organization)
            if invalid_cls.exists():
                msg = (
                    f"[Teacher] {teacher} : 異なる組織の教室を切り離し -> "
                    f"{[c.name for c in invalid_cls]}"
                )
                result["changes"].append(msg)
                if not dry_run:
                    teacher.classrooms.remove(*invalid_cls)

        # 3) Student との矛盾は「検出のみ」。組織をまたいで担当している場合は危険なので自動修正しない
        if teacher.organization:
            cross_org_students = t_students.exclude(organization=teacher.organization)
            if cross_org_students.exists():
                msg = (
                    f"[Teacher] {teacher} : 異なる組織の生徒を担当 -> "
                    f"{[s.username for s in cross_org_students]}"
                )
                result["warnings"].append(msg)


    # --- Student の organization 補完 & 不正教室の切り離し ---
    for student in Student.objects.all():
        s_classrooms = student.classrooms.all()

        # organization があるのに、別組織の教室をぶら下げている場合 → その教室だけ外す
        if student.organization:
            invalid_cls = s_classrooms.exclude(organization=student.organization)
            if invalid_cls.exists():
                msg = (
                    f"[Student] {student} : 異なる組織の教室を切り離し -> "
                    f"{[c.name for c in invalid_cls]}"
                )
                result["changes"].append(msg)
                if not dry_run:
                    student.classrooms.remove(*invalid_cls)

    return result


def fix_teacher_classrooms_from_students(dry_run=True):
    """
    生徒を通じて教室に関与しているのに、
    Teacher.classrooms が不足している講師を補完する
    """
    updated = []

    for teacher in Teacher.objects.all():
        # 生徒を通じて関係している教室
        cls_via_students = Classroom.objects.filter(
            students__in=teacher.students.all()
        ).distinct()

        if not cls_via_students.exists():
            continue  # 生徒を担当していない / 教室とも無関係

        # 組織と不整合な教室は除外
        if teacher.organization_id:
            cls_via_students = cls_via_students.filter(
                organization_id=teacher.organization_id
            )

        # すでに classrooms に入っているものは除外
        missing = cls_via_students.exclude(
            id__in=teacher.classrooms.values_list("id", flat=True)
        )

        if missing.exists():
            if dry_run:
                print(f"[DRY-RUN] Teacher {teacher} will be linked to: "
                    f"{[c.name for c in missing]}")
            else:
                teacher.classrooms.add(*missing)
                updated.append((teacher, list(missing)))

    return updated
