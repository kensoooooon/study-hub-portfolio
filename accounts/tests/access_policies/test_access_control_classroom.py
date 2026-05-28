"""
教室レベルのアクセス制御＆「教室の壁」を検証するテスト群。

主な対象:
    - Organization.can_be_accessed_by
    - Classroom.can_be_accessed_by
    - OrganizationAdministrator.can_manage_classroom / can_manage_student
    - ClassroomAdministrator.can_manage_classroom / can_manage_student
    - Teacher.can_be_accessed_by / can_manage_student / get_students

前提となるモデル定義:
    - Organization / Classroom: accounts.organization_models.Organization, Classroom
    - Student / Teacher / ClassroomAdministrator / OrganizationAdministrator:
      accounts.user_models の各モデル
"""

from django.test import TestCase
from accounts.models import (
    Organization,
    Classroom,
    Student,
    Teacher,
    ClassroomAdministrator,
    OrganizationAdministrator,
)


class ClassroomAccessControlTests(TestCase):
    """
    Classroom.can_be_accessed_by の挙動を検証する。

    Classroom.can_be_accessed_by(user) の仕様:
        - organization_administrator:
            → classroom.organization.administrators に含まれている場合のみ True
        - classroom_administrator:
            → classroom.administrators に含まれている場合のみ True
        - それ以外: False
    """

    def setUp(self):
        # 組織を2つ
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        # Org1 に教室を2つ、Org2 に教室を1つ
        self.classroom1_org1 = Classroom.objects.create(
            name="Org1-Classroom1",
            organization=self.org1,
        )
        self.classroom2_org1 = Classroom.objects.create(
            name="Org1-Classroom2",
            organization=self.org1,
        )
        self.classroom1_org2 = Classroom.objects.create(
            name="Org2-Classroom1",
            organization=self.org2,
        )

        # 組織管理者
        self.org_admin1 = OrganizationAdministrator.objects.create(
            email="org_admin1@example.com",
            username="OrgAdmin1",
            role="organization_administrator",
        )
        self.org_admin1.organizations.add(self.org1)

        self.org_admin2 = OrganizationAdministrator.objects.create(
            email="org_admin2@example.com",
            username="OrgAdmin2",
            role="organization_administrator",
        )
        self.org_admin2.organizations.add(self.org2)

        # 教室管理者（Org1-Classroom1 専任）
        self.classroom_admin1 = ClassroomAdministrator.objects.create(
            email="ca1@example.com",
            username="ClassroomAdmin1",
            role="classroom_administrator",
            organization=self.org1,
        )
        self.classroom_admin1.classrooms.add(self.classroom1_org1)

        # 教室管理者（Org1-Classroom2 専任）
        self.classroom_admin2 = ClassroomAdministrator.objects.create(
            email="ca2@example.com",
            username="ClassroomAdmin2",
            role="classroom_administrator",
            organization=self.org1,
        )
        self.classroom_admin2.classrooms.add(self.classroom2_org1)

    def test_classroom_accessible_by_own_org_admin(self):
        """
        組織管理者は、自身の管理する組織に属する教室であればアクセス可能。
        """
        self.assertTrue(self.classroom1_org1.can_be_accessed_by(self.org_admin1))
        self.assertTrue(self.classroom2_org1.can_be_accessed_by(self.org_admin1))

        self.assertTrue(self.classroom1_org2.can_be_accessed_by(self.org_admin2))

    def test_classroom_not_accessible_by_other_org_admin(self):
        """
        組織が異なる組織管理者は、該当教室にアクセスできない。
        """
        self.assertFalse(self.classroom1_org1.can_be_accessed_by(self.org_admin2))
        self.assertFalse(self.classroom1_org2.can_be_accessed_by(self.org_admin1))

    def test_classroom_accessible_only_by_own_classroom_admin(self):
        """
        教室管理者は、自分が管理する教室にだけアクセスできる。
        同じ組織内の別教室はアクセス不可。
        """
        # Classroom1 は classroom_admin1 の教室
        self.assertTrue(self.classroom1_org1.can_be_accessed_by(self.classroom_admin1))
        self.assertFalse(self.classroom2_org1.can_be_accessed_by(self.classroom_admin1))

        # Classroom2 は classroom_admin2 の教室
        self.assertTrue(self.classroom2_org1.can_be_accessed_by(self.classroom_admin2))
        self.assertFalse(self.classroom1_org1.can_be_accessed_by(self.classroom_admin2))

        # Org2 の教室は、Org1 所属の教室管理者からは見えない
        self.assertFalse(self.classroom1_org2.can_be_accessed_by(self.classroom_admin1))
        self.assertFalse(self.classroom1_org2.can_be_accessed_by(self.classroom_admin2))


class OrganizationAccessControlTests(TestCase):
    """
    Organization.can_be_accessed_by の挙動を検証する。

    Organization.can_be_accessed_by(user) の仕様:
        - organization_administrator:
            → self.administrators に含まれる場合 True
        - classroom_administrator:
            → self.classrooms のいずれかに user が administrator として紐付いている場合 True
    """

    def setUp(self):
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        self.classroom_org1 = Classroom.objects.create(
            name="Org1-Classroom",
            organization=self.org1,
        )
        self.classroom_org2 = Classroom.objects.create(
            name="Org2-Classroom",
            organization=self.org2,
        )

        self.org_admin1 = OrganizationAdministrator.objects.create(
            email="org_admin1@example.com",
            username="OrgAdmin1",
            role="organization_administrator",
        )
        self.org_admin1.organizations.add(self.org1)

        self.org_admin2 = OrganizationAdministrator.objects.create(
            email="org_admin2@example.com",
            username="OrgAdmin2",
            role="organization_administrator",
        )
        self.org_admin2.organizations.add(self.org2)

        self.classroom_admin1 = ClassroomAdministrator.objects.create(
            email="ca1@example.com",
            username="ClassroomAdmin1",
            role="classroom_administrator",
            organization=self.org1,
        )
        self.classroom_admin1.classrooms.add(self.classroom_org1)

        self.classroom_admin2 = ClassroomAdministrator.objects.create(
            email="ca2@example.com",
            username="ClassroomAdmin2",
            role="classroom_administrator",
            organization=self.org2,
        )
        self.classroom_admin2.classrooms.add(self.classroom_org2)

    def test_organization_accessible_by_own_org_admin(self):
        self.assertTrue(self.org1.can_be_accessed_by(self.org_admin1))
        self.assertTrue(self.org2.can_be_accessed_by(self.org_admin2))

    def test_organization_not_accessible_by_other_org_admin(self):
        self.assertFalse(self.org1.can_be_accessed_by(self.org_admin2))
        self.assertFalse(self.org2.can_be_accessed_by(self.org_admin1))

    def test_organization_accessible_by_classroom_admin_of_its_classrooms(self):
        """
        その組織の教室を管理している classroom_admin は
        組織にもアクセス可能であることを確認。
        """
        self.assertTrue(self.org1.can_be_accessed_by(self.classroom_admin1))
        self.assertFalse(self.org1.can_be_accessed_by(self.classroom_admin2))

        self.assertTrue(self.org2.can_be_accessed_by(self.classroom_admin2))
        self.assertFalse(self.org2.can_be_accessed_by(self.classroom_admin1))


class ClassroomAdminManageStudentTests(TestCase):
    """
    ClassroomAdministrator.can_manage_student の挙動を検証する。

    仕様:
        - classroom_admin が管理する教室に所属する生徒だけ True
        - 同じ組織内でも、別教室の生徒は False
    """

    def setUp(self):
        self.org1 = Organization.objects.create(name="Org 1")

        self.classroom1 = Classroom.objects.create(
            name="Org1-Classroom1",
            organization=self.org1,
        )
        self.classroom2 = Classroom.objects.create(
            name="Org1-Classroom2",
            organization=self.org1,
        )

        self.classroom_admin1 = ClassroomAdministrator.objects.create(
            email="ca1@example.com",
            username="ClassroomAdmin1",
            role="classroom_administrator",
            organization=self.org1,
        )
        self.classroom_admin1.classrooms.add(self.classroom1)

        self.classroom_admin2 = ClassroomAdministrator.objects.create(
            email="ca2@example.com",
            username="ClassroomAdmin2",
            role="classroom_administrator",
            organization=self.org1,
        )
        self.classroom_admin2.classrooms.add(self.classroom2)

        # 生徒は同じ組織に所属
        self.student_in_c1 = Student.objects.create(
            username="Student-C1",
            line_user_id="U-STUDENT-C1",
            organization=self.org1,
        )
        self.student_in_c1.classrooms.add(self.classroom1)

        self.student_in_c2 = Student.objects.create(
            username="Student-C2",
            line_user_id="U-STUDENT-C2",
            organization=self.org1,
        )
        self.student_in_c2.classrooms.add(self.classroom2)

    def test_classroom_admin_can_manage_students_in_own_classrooms_only(self):
        """
        教室管理者は、自分の管理教室に所属する生徒だけ管理できる。
        """
        # Admin1 は classroom1 の生徒だけ管理可能
        self.assertTrue(self.classroom_admin1.can_manage_student(self.student_in_c1))
        self.assertFalse(self.classroom_admin1.can_manage_student(self.student_in_c2))

        # Admin2 は classroom2 の生徒だけ管理可能
        self.assertTrue(self.classroom_admin2.can_manage_student(self.student_in_c2))
        self.assertFalse(self.classroom_admin2.can_manage_student(self.student_in_c1))


class OrganizationAdminManageStudentTests(TestCase):
    """
    OrganizationAdministrator.can_manage_student の挙動を検証する。

    仕様:
        - 管理する組織に属する教室に所属する生徒であれば True
        - 異なる組織の生徒は False
    """

    def setUp(self):
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        self.classroom1_org1 = Classroom.objects.create(
            name="Org1-Classroom1",
            organization=self.org1,
        )
        self.classroom1_org2 = Classroom.objects.create(
            name="Org2-Classroom1",
            organization=self.org2,
        )

        self.org_admin1 = OrganizationAdministrator.objects.create(
            email="org_admin1@example.com",
            username="OrgAdmin1",
            role="organization_administrator",
        )
        self.org_admin1.organizations.add(self.org1)

        # Org1 の生徒
        self.student_org1 = Student.objects.create(
            username="Student-Org1",
            line_user_id="U-STUDENT-ORG1",
            organization=self.org1,
        )
        self.student_org1.classrooms.add(self.classroom1_org1)

        # Org2 の生徒
        self.student_org2 = Student.objects.create(
            username="Student-Org2",
            line_user_id="U-STUDENT-ORG2",
            organization=self.org2,
        )
        self.student_org2.classrooms.add(self.classroom1_org2)

    def test_org_admin_can_manage_only_students_in_managed_organizations(self):
        self.assertTrue(self.org_admin1.can_manage_student(self.student_org1))
        self.assertFalse(self.org_admin1.can_manage_student(self.student_org2))


class TeacherAccessControlAndStudentsTests(TestCase):
    """
    Teacher.can_be_accessed_by / get_students / can_manage_student をまとめて検証。

    Teacher.can_be_accessed_by(user) の仕様:
        - organization_administrator:
            → teacher.classrooms の organization が admin.organizations に含まれていれば True
        - classroom_administrator:
            → teacher.classrooms に admin.classrooms のいずれかが含まれていれば True
    """

    def setUp(self):
        self.org1 = Organization.objects.create(name="Org 1")
        self.org2 = Organization.objects.create(name="Org 2")

        self.classroom1_org1 = Classroom.objects.create(
            name="Org1-Classroom1",
            organization=self.org1,
        )
        self.classroom2_org1 = Classroom.objects.create(
            name="Org1-Classroom2",
            organization=self.org1,
        )
        self.classroom1_org2 = Classroom.objects.create(
            name="Org2-Classroom1",
            organization=self.org2,
        )

        # 組織管理者
        self.org_admin1 = OrganizationAdministrator.objects.create(
            email="org_admin1@example.com",
            username="OrgAdmin1",
            role="organization_administrator",
        )
        self.org_admin1.organizations.add(self.org1)

        self.org_admin2 = OrganizationAdministrator.objects.create(
            email="org_admin2@example.com",
            username="OrgAdmin2",
            role="organization_administrator",
        )
        self.org_admin2.organizations.add(self.org2)

        # 教室管理者
        self.classroom_admin1 = ClassroomAdministrator.objects.create(
            email="ca1@example.com",
            username="ClassroomAdmin1",
            role="classroom_administrator",
            organization=self.org1,
        )
        self.classroom_admin1.classrooms.add(self.classroom1_org1)

        self.classroom_admin2 = ClassroomAdministrator.objects.create(
            email="ca2@example.com",
            username="ClassroomAdmin2",
            role="classroom_administrator",
            organization=self.org2,
        )
        self.classroom_admin2.classrooms.add(self.classroom1_org2)

        # Org1 に所属する講師（classroom1_org1 を担当）
        self.teacher_org1 = Teacher.objects.create(
            username="Teacher-Org1",
            email="teacher_org1@example.com",
            role="teacher",
            organization=self.org1,
        )
        self.teacher_org1.classrooms.add(self.classroom1_org1)

        # Org2 に所属する講師（classroom1_org2 を担当）
        self.teacher_org2 = Teacher.objects.create(
            username="Teacher-Org2",
            email="teacher_org2@example.com",
            role="teacher",
            organization=self.org2,
        )
        self.teacher_org2.classrooms.add(self.classroom1_org2)

        # 生徒を数人作成し、担当講師を紐付け
        self.student1 = Student.objects.create(
            username="Student1",
            line_user_id="U-STUDENT1",
            organization=self.org1,
            grade=7,
        )
        self.student1.teachers.add(self.teacher_org1)
        self.student1.classrooms.add(self.classroom1_org1)

        self.student2 = Student.objects.create(
            username="Student2",
            line_user_id="U-STUDENT2",
            organization=self.org1,
            grade=8,
        )
        self.student2.teachers.add(self.teacher_org1)
        self.student2.classrooms.add(self.classroom1_org1)

        self.student_other_org = Student.objects.create(
            username="Student-OtherOrg",
            line_user_id="U-STUDENT-OTHER",
            organization=self.org2,
        )
        self.student_other_org.teachers.add(self.teacher_org2)
        self.student_other_org.classrooms.add(self.classroom1_org2)

    def test_teacher_can_be_accessed_by_org_and_classroom_admin(self):
        """
        Teacher.can_be_accessed_by のアクセス制御をテスト。
        """
        # Org1 の講師は Org1 のorg_adminから見えるが、Org2 からは見えない
        self.assertTrue(self.teacher_org1.can_be_accessed_by(self.org_admin1))
        self.assertFalse(self.teacher_org1.can_be_accessed_by(self.org_admin2))

        # Org2 の講師は Org2 のorg_adminから見えるが、Org1 からは見えない
        self.assertTrue(self.teacher_org2.can_be_accessed_by(self.org_admin2))
        self.assertFalse(self.teacher_org2.can_be_accessed_by(self.org_admin1))

        # classroom_admin1 は classroom1_org1 を担当しているので teacher_org1 を見られる
        self.assertTrue(self.teacher_org1.can_be_accessed_by(self.classroom_admin1))
        # 逆に Org2 の講師は見えない
        self.assertFalse(self.teacher_org2.can_be_accessed_by(self.classroom_admin1))

        # classroom_admin2 は Org2 の教室を担当しているので teacher_org2 のみ見える
        self.assertTrue(self.teacher_org2.can_be_accessed_by(self.classroom_admin2))
        self.assertFalse(self.teacher_org1.can_be_accessed_by(self.classroom_admin2))

    def test_teacher_get_students_and_can_manage_student(self):
        """
        Teacher.get_students / can_manage_student が正しい生徒集合を返すかを確認。
        """
        students = list(self.teacher_org1.get_students())
        self.assertIn(self.student1, students)
        self.assertIn(self.student2, students)
        self.assertNotIn(self.student_other_org, students)

        # can_manage_student は自分の担当生徒のみ True
        self.assertTrue(self.teacher_org1.can_manage_student(self.student1))
        self.assertTrue(self.teacher_org1.can_manage_student(self.student2))
        self.assertFalse(self.teacher_org1.can_manage_student(self.student_other_org))
