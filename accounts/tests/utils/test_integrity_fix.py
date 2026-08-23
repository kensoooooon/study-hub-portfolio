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

    def test_student_invalid_classrooms_are_removed(self):
        """生徒の org と異なる教室は自動的に切り離される"""
        student = Student.objects.create_user(
            email="s2@example.com",
            password="pass",
            username="Student2",
            organization=self.org1,
        )

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

    def test_classroom_administrator_invalid_classrooms_are_removed(self):
        """
        教室管理者が管理する教室のうち、所属組織(organization)と異なる教室が
        fix_org_classroom_integrity()により自動的に切り離されることを確認する。

        この関数内の比較を`organization=ca.organization`(関連オブジェクト経由)
        から`organization_id=ca.organization_id`(FK直接比較)へ変更したが、
        教室管理者分岐は変更前から自動テストが存在しなかったため、
        今回新規追加する回帰テスト(意味を変えない書き換えであることを担保する)。
        """
        ca = ClassroomAdministrator.objects.create_user(
            email="ca1@example.com",
            password="pass",
            username="CA1",
            organization=self.org1,
        )

        # 正しい教室（org1）は正式ルートで紐付ける
        ca.classrooms.add(self.class1_org1)

        # m2mでガードされてしまうので、org2 の教室だけは中間テーブルに直接挿入
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts_classroomadministrator_classrooms "
                "(classroomadministrator_id, classroom_id) VALUES (%s, %s)",
                [ca.pk, self.class2_org2.pk],
            )

        fix_org_classroom_integrity(dry_run=False)

        ca.refresh_from_db()
        # org1 の教室だけが残っている
        self.assertQuerySetEqual(
            ca.classrooms.all(),
            [self.class1_org1],
            transform=lambda x: x,
        )

    def test_teacher_invalid_classrooms_are_removed(self):
        """
        講師が担当する教室のうち、所属組織(organization)と異なる教室が
        fix_org_classroom_integrity()により自動的に切り離されることを確認する。

        `organization=teacher.organization`→`organization_id=teacher.organization_id`
        変更に伴う回帰テスト(講師分岐はこの変更前から自動テストが存在しなかった)。
        """
        teacher = Teacher.objects.create_user(
            email="t1@example.com",
            password="pass",
            username="Teacher1",
            organization=self.org1,
        )

        # 正しい教室（org1）は正式ルートで紐付ける
        teacher.classrooms.add(self.class1_org1)

        # m2mでガードされてしまうので、org2 の教室だけは中間テーブルに直接挿入
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts_teacher_classrooms (teacher_id, classroom_id) "
                "VALUES (%s, %s)",
                [teacher.pk, self.class2_org2.pk],
            )

        fix_org_classroom_integrity(dry_run=False)

        teacher.refresh_from_db()
        # org1 の教室だけが残っている
        self.assertQuerySetEqual(
            teacher.classrooms.all(),
            [self.class1_org1],
            transform=lambda x: x,
        )

    def test_teacher_cross_org_student_produces_warning_without_modification(self):
        """
        講師が所属組織(organization)と異なる組織の生徒を担当している場合、
        fix_org_classroom_integrity()はwarningsに記録するのみで、
        担当関係の自動修正はしないことを確認する。

        `organization=teacher.organization`→`organization_id=teacher.organization_id`
        変更に伴う回帰テスト(この検出のみ・自動修正なしの分岐はこの変更前から自動テストが
        存在しなかった)。
        """
        teacher = Teacher.objects.create_user(
            email="t2@example.com",
            password="pass",
            username="Teacher2",
            organization=self.org1,
        )
        other_org_student = Student.objects.create_user(
            email="s3@example.com",
            password="pass",
            username="Student3",
            organization=self.org2,
        )

        # Student.teachers はm2m_changedでガードされるので中間テーブルに直接挿入
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts_student_teachers (student_id, teacher_id) "
                "VALUES (%s, %s)",
                [other_org_student.pk, teacher.pk],
            )

        res = fix_org_classroom_integrity(dry_run=False)

        self.assertTrue(
            any("異なる組織の生徒を担当" in w for w in res["warnings"])
        )
        # 検出のみで自動修正はしない仕様のため、担当関係はそのまま残っている
        self.assertIn(other_org_student, teacher.students.all())

