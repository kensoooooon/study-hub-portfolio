"""
既存データの矛盾の検知、修正が正常に動作しているかのチェック
"""

from django.test import TestCase
from accounts.models import (
    Organization,
    Classroom,
    Student,
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

