"""
既存データの矛盾の検知、修正が正常に動作しているかのチェック
"""

from django.test import TestCase
from accounts.models import (
    Organization,
    Classroom,
    Student,
    Teacher,
    ClassroomAdministrator,
)
from accounts.utils.integrity_fix import fix_org_classroom_integrity


class IntegrityFixTests(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="Org1")
        self.org2 = Organization.objects.create(name="Org2")

        self.class1_org1 = Classroom.objects.create(
            name="Org1-Class",
            organization=self.org1,
        )
        self.class2_org2 = Classroom.objects.create(
            name="Org2-Class",
            organization=self.org2,
        )

    def test_student_org_none_adopts_classroom_org(self):
        """organization=None の生徒が、所属教室の組織を引き継ぐ"""
        student = Student.objects.create_user(
            email="s1@example.com",
            password="pass",
            username="Student1",
        )
        student.organization = None
        student.save()
        student.classrooms.add(self.class1_org1)

        res = fix_org_classroom_integrity(dry_run=False)

        student.refresh_from_db()
        self.assertEqual(student.organization, self.org1)
        # 教室が切り離されていないことも確認
        self.assertQuerySetEqual(
            student.classrooms.all(),
            [self.class1_org1],
            transform=lambda x: x,
        )

    def test_student_invalid_classrooms_are_removed(self):
        """生徒の org と異なる教室は自動的に切り離される"""
        student = Student.objects.create_user(
            email="s2@example.com",
            password="pass",
            username="Student2",
        )
        student.organization = self.org1
        student.save()

        # 正しい教室（org1）は正式ルートで紐付ける
        student.classrooms.add(self.class1_org1)

        # m2mでガードされてしまうので、org2 の教室だけは中間テーブルに直接挿入
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts_student_classrooms (student_id, classroom_id) "
                "VALUES (%s, %s)",
                [student.pk, self.class2_org2.pk],
            )

        res = fix_org_classroom_integrity(dry_run=False)

        student.refresh_from_db()
        # org1 の教室だけが残っている
        self.assertQuerySetEqual(
            student.classrooms.all(),
            [self.class1_org1],
            transform=lambda x: x,
        )

    def test_classroom_admin_org_none_adopts_classroom_org(self):
        """CA: organization=None + 管理教室あり -> 教室の組織を引き継ぐ"""
        ca = ClassroomAdministrator.objects.create_user(
            email="ca@example.com",
            password="pass",
            username="CA",
        )
        ca.organization = None
        ca.save()
        ca.classrooms.add(self.class1_org1)

        res = fix_org_classroom_integrity(dry_run=False)

        ca.refresh_from_db()
        self.assertEqual(ca.organization, self.org1)

    def test_teacher_org_none_adopts_unique_classroom_org(self):
        """Teacher: organization=None + 管理教室が単一組織 -> その組織を引き継ぐ"""
        teacher = Teacher.objects.create_user(
            email="t1@example.com",
            password="pass",
            username="Teacher1",
        )
        teacher.organization = None
        teacher.save()
        teacher.classrooms.add(self.class1_org1)

        res = fix_org_classroom_integrity(dry_run=False)

        teacher.refresh_from_db()
        self.assertEqual(teacher.organization, self.org1)

    def test_teacher_ambiguous_org_not_changed(self):
        """Teacher: 異なる組織の教室を複数持つ場合は organization を自動決定しない"""
        teacher = Teacher.objects.create_user(
            email="t2@example.com",
            password="pass",
            username="Teacher2",
        )
        teacher.organization = None
        teacher.save()
        teacher.classrooms.add(self.class1_org1, self.class2_org2)

        res = fix_org_classroom_integrity(dry_run=False)

        teacher.refresh_from_db()
        # 組織は決められていないはず
        self.assertIsNone(teacher.organization)
        # 両方の教室は残したまま（警告対象）
        self.assertEqual(
            set(teacher.classrooms.all()),
            {self.class1_org1, self.class2_org2},
        )
        # warning が 1 件以上出ていることだけ軽く確認
        self.assertTrue(any("Teacher" in w for w in res["warnings"]))
