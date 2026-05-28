"""
生徒自身が自分を取得するための関数テスト

- 基本方針
    - 未認証ユーザーは何も得られない
    - 生徒以外のロールも何も得られない
    - 生徒だけが唯一自身を取得可能
"""

from django.test import TestCase
from django.contrib.auth.models import AnonymousUser


from accounts.models import (
    Student,
    Teacher,
    ClassroomAdministrator,
    OrganizationAdministrator,
    Classroom,
    Organization
)
from accounts.selectors import get_visible_self_student

class GetVisibleSelfStudentTest(TestCase):
    """
    生徒が自分自身を正しく取得できることを確認するためのテスト
    """
    @classmethod
    def setUpTestData(cls):
        # 自テナント
        cls.org1 = Organization.objects.create(name="Organization 1")
        cls.org_admin1 = OrganizationAdministrator.objects.create_user(
            username="Org Admin1",
            email="org_admin1@example.com",
            password="pass123456"
        )
        cls.org_admin1.organizations.add(cls.org1)

        cls.classroom1 = Classroom.objects.create(name="ClassRoom 1", organization=cls.org1)

        # 対象が所属する組織管理者
        cls.classroom_admin1 = ClassroomAdministrator.objects.create_user(
            username="Classroom Admin1",
            email="classroom_admin1@example.com",
            password="pass123456",
            organization=cls.org1
        )
        cls.classroom_admin1.classrooms.add(cls.classroom1)

        # 同じ組織だが、対象生徒が属さない教室とその管理者
        cls.classroom1_2 = Classroom.objects.create(name="ClassRoom 1_2", organization=cls.org1)
        cls.classroom_admin1_2 = ClassroomAdministrator.objects.create_user(
            username="Classroom Admin1_2",
            email="classroom_admin1_2@example.com",
            password="pass123456",
            organization=cls.org1
        )
        cls.classroom_admin1_2.classrooms.add(cls.classroom1_2)

        # 同じ組織で、対象を担当している講師
        cls.teacher1 = Teacher.objects.create_user(
            username="Teacher1",
            email="teacher1@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.teacher1.classrooms.add(cls.classroom1)

        # 対象生徒を担当していない講師
        cls.teacher1_2 = Teacher.objects.create_user(
            username="Teacher1_2",
            email="teacher1_2@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.teacher1_2.classrooms.add(cls.classroom1)

        # 対象生徒
        cls.student1 = Student.objects.create_user(
            username="Sample Student1",
            email="student1@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.student1.classrooms.add(cls.classroom1)
        cls.student1.teachers.add(cls.teacher1)

        # 別の生徒(同じ教室・同じ組織)
        cls.student_actor1 = Student.objects.create_user(
            username="Student Actor1",
            email="student_actor1@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.student_actor1.classrooms.add(cls.classroom1)
        # 別の生徒(異なる教室・同じ組織)
        cls.student_actor1_2 = Student.objects.create_user(
            username="Student Actor1_2",
            email="student_actor1_2@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.student_actor1_2.classrooms.add(cls.classroom1_2)

        # 別テナント
        cls.org2 = Organization.objects.create(name="Organization 2")
        cls.org_admin2 = OrganizationAdministrator.objects.create_user(
            username="Org Admin2",
            email="org_admin2@example.com",
            password="pass123456"
        )
        cls.org_admin2.organizations.add(cls.org2)

        cls.classroom2 = Classroom.objects.create(name="ClassRoom 2", organization=cls.org2)

        cls.student_actor2 = Student.objects.create_user(
            username="Student Actor2",
            email="student_actor2@example.com",
            password="pass123456",
            organization=cls.org2,
        )
        cls.student_actor2.classrooms.add(cls.classroom2)
    
    def test_anonymous_cannot_acquire_anything(self):
        """
        未ログインユーザーは何も得られない
        """
        s = get_visible_self_student(AnonymousUser())
        self.assertIsNone(s)

    def test_org_admin_cannot_acquire_anything(self):
        """
        組織管理者は何も得られない
        """
        s = get_visible_self_student(self.org_admin1)
        self.assertIsNone(s)

    def test_class_room_admin_cannot_acquire_anything(self):
        """
        教室管理者は何も得られない
        """
        s = get_visible_self_student(self.classroom_admin1)
        self.assertIsNone(s)

    def test_teacher_cannot_acquire_anything(self):
        """
        講師は何も得られない
        """
        s = get_visible_self_student(self.teacher1)
        self.assertIsNone(s)
    
    def test_student_can_acquire_self(self):
        """
        生徒は自分自身を得られる
        """
        s = get_visible_self_student(self.student1)
        self.assertEqual(s.pk, self.student1.pk)
    
    def test_student_cannot_acquire_other_students(self):
        """
        生徒は自分自身以外の生徒を取得することはできない
        """
        s = get_visible_self_student(self.student1)
        self.assertNotEqual(s.pk, self.student_actor1.pk)
        self.assertNotEqual(s.pk, self.student_actor1_2.pk)
        self.assertNotEqual(s.pk, self.student_actor2.pk)

    def test_inactive_student_cannot_acquire_self(self):
        """
        非アクティブの生徒は生徒自身であっても取得できない
        """
        self.student1.is_active = False
        self.student1.save()

        s = get_visible_self_student(self.student1)
        self.assertIsNone(s)
