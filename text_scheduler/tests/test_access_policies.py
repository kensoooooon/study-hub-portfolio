"""
text_scheduler/access_policies.py の visible_students_qs について、
組織管理者(organization_administrator)・教室管理者(classroom_administrator)の
テナント境界とis_active(非アクティブ生徒の除外)を確認するテスト。
"""
from django.test import TestCase

from accounts.models import (
    Classroom,
    ClassroomAdministrator,
    Organization,
    OrganizationAdministrator,
    Student,
)
from text_scheduler.access_policies import visible_students_qs


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
        cls.org1_inactive_student = Student.objects.create_user(
            username="org1_inactive_student",
            email="org1_inactive_student@example.com",
            password="pass12345",
            organization=cls.org1,
            is_active=False,
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

    def test_org_admin_does_not_see_inactive_student_in_own_organization(self):
        """
        Issue #120の回帰防止テスト。
        組織管理者は、自分が管理する組織内であっても、
        is_active=False(ソフト削除済み)の生徒をvisible_students_qsで取得できないことを確認する。
        """
        qs = visible_students_qs(self.org1_admin)
        self.assertNotIn(self.org1_inactive_student, qs)


class VisibleStudentsQsClassroomAdminTests(TestCase):
    """
    教室管理者が visible_students_qs 経由で取得できる生徒の範囲を確認する。
    このロールの可視範囲テストはこれまで存在しなかったため、新規に追加する。
    """

    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="Org1")
        cls.classroom1 = Classroom.objects.create(name="Classroom1", organization=cls.org1)

        cls.classroom1_admin = ClassroomAdministrator.objects.create_user(
            email="classroom1_admin@example.com",
            username="classroom1_admin",
            password="pass12345",
            role="classroom_administrator",
            organization=cls.org1,
        )
        cls.classroom1_admin.classrooms.add(cls.classroom1)

        cls.active_student = Student.objects.create_user(
            username="classroom1_active_student",
            email="classroom1_active_student@example.com",
            password="pass12345",
            organization=cls.org1,
            is_active=True,
        )
        cls.active_student.classrooms.add(cls.classroom1)

        cls.inactive_student = Student.objects.create_user(
            username="classroom1_inactive_student",
            email="classroom1_inactive_student@example.com",
            password="pass12345",
            organization=cls.org1,
            is_active=False,
        )
        cls.inactive_student.classrooms.add(cls.classroom1)

    def test_classroom_admin_sees_active_student_in_own_classroom(self):
        """
        教室管理者は、自分が管理する教室のアクティブな生徒をvisible_students_qsで取得できる。
        """
        qs = visible_students_qs(self.classroom1_admin)
        self.assertIn(self.active_student, qs)

    def test_classroom_admin_does_not_see_inactive_student_in_own_classroom(self):
        """
        Issue #120の回帰防止テスト。
        教室管理者は、自分が管理する教室内であっても、
        is_active=False(ソフト削除済み)の生徒をvisible_students_qsで取得できないことを確認する。
        """
        qs = visible_students_qs(self.classroom1_admin)
        self.assertNotIn(self.inactive_student, qs)
