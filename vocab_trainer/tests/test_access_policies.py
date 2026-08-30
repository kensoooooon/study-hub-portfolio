"""
vocab_trainer/access_policies.py の visible_students_qs について、
組織管理者(organization_administrator)のテナント境界を確認するテスト。
"""
from django.test import TestCase

from accounts.models import Organization, OrganizationAdministrator, Student
from vocab_trainer.access_policies import (
    student_can_be_accessed_by,
    visible_students_qs,
)


class VisibleStudentsQsOrgAdminTests(TestCase):
    """
    組織管理者が visible_students_qs 経由で取得できる生徒の範囲を確認する。
    """

    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="Org1")
        cls.org2 = Organization.objects.create(name="Org2")

        cls.org1_admin = OrganizationAdministrator.objects.create_user(
            email="org1_admin@example.com",
            username="org1_admin",
            password="pass12345",
            role="organization_administrator",
            organization=cls.org1,
        )

        cls.org1_student = Student.objects.create_user(
            username="org1_student",
            email="org1_student@example.com",
            password="pass12345",
            organization=cls.org1,
            is_active=True,
        )
        cls.org2_student = Student.objects.create_user(
            username="org2_student",
            email="org2_student@example.com",
            password="pass12345",
            organization=cls.org2,
            is_active=True,
        )

    def test_org_admin_sees_students_in_own_organization(self):
        """
        組織管理者は、自分が管理する組織の生徒をvisible_students_qsで取得できる。
        """
        qs = visible_students_qs(self.org1_admin)
        self.assertIn(self.org1_student, qs)

    def test_org_admin_does_not_see_students_in_other_organization(self):
        """
        組織管理者は、自分が管理しない組織の生徒をvisible_students_qsで取得できない。
        """
        qs = visible_students_qs(self.org1_admin)
        self.assertNotIn(self.org2_student, qs)

    def test_is_superuser_flag_does_not_widen_visible_students_qs(self):
        """
        is_superuserフラグが立っていても、visible_students_qsの可視範囲は
        roleとテナントスコープのみで決まり、他組織の生徒は見えないことを確認する回帰テスト。

        Issue #162でaccess_policiesから `if user.is_superuser: return qs` の
        早期returnを撤去したことを固定する。is_superuser=Trueの行は生成不可のため
        メモリ上でフラグを立てる。
        """
        self.org1_admin.is_superuser = True  # DBへは保存しない

        qs = visible_students_qs(self.org1_admin)

        self.assertIn(self.org1_student, qs)
        self.assertNotIn(self.org2_student, qs)

    def test_is_superuser_flag_does_not_widen_student_can_be_accessed_by(self):
        """
        is_superuserフラグが立っていても、student_can_be_accessed_byは
        可視範囲QSに含まれるかで判定され、他組織の生徒へはFalseとなることを確認する回帰テスト。
        """
        self.org1_admin.is_superuser = True  # DBへは保存しない

        self.assertTrue(
            student_can_be_accessed_by(self.org1_admin, self.org1_student)
        )
        self.assertFalse(
            student_can_be_accessed_by(self.org1_admin, self.org2_student)
        )
