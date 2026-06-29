"""
最大可視範囲の生徒の取得テスト

- 基本方針
    - 組織管理者は、自身の管理している組織に所属する生徒
    - 教室管理者は、自身の管理している組織に所属する生徒
    - 講師は、自身の担当している生徒
    - 生徒は自身を含めて、何も取得できない
"""

from django.test import TestCase
from django.contrib.auth.models import AnonymousUser
from unittest.mock import Mock


from accounts.models import (
    Student,
    Teacher,
    ClassroomAdministrator,
    OrganizationAdministrator,
    Classroom,
    Organization
)
from accounts.selectors import visible_students_qs

class VisibleStudentsTest(TestCase):
    """
    生徒の可視範囲が設定したものになっていることを確認するためのテスト
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

        cls.classroom_admin2 = ClassroomAdministrator.objects.create_user(
            username="Classroom Admin2",
            email="classroom_admin2@example.com",
            password="pass123456",
            organization=cls.org2
        )
        cls.classroom_admin2.classrooms.add(cls.classroom2)

        cls.teacher2 = Teacher.objects.create_user(
            username="Teacher2",
            email="teacher2@example.com",
            password="pass123456",
            organization=cls.org2,
        )
        cls.teacher2.classrooms.add(cls.classroom2)

        cls.student_actor2 = Student.objects.create_user(
            username="Student Actor2",
            email="student_actor2@example.com",
            password="pass123456",
            organization=cls.org2,
        )
        cls.student_actor2.classrooms.add(cls.classroom2)

    def test_same_tenant_org_admin_can_see_students(self):
        """
        組織管理者は自身の組織に所属している生徒を取得可能
        """
        qs = visible_students_qs(self.org_admin1)
        self.assertIn(self.student1, qs) # 組織1・組織1
        self.assertIn(self.student_actor1, qs)  # 組織1・教室1
        self.assertIn(self.student_actor1_2, qs)  #組織1・教室2
        self.assertNotIn(self.student_actor2, qs)  # 別テナント防御
        self.assertEqual(qs.count(), 3)  # 過剰に取得していないか
    
    def test_same_tenant_classroom_admin_can_see_students(self):
        """
        教室管理者は自分の担当している教室の生徒は見れるが、そうでない生徒は同じ組織でも見られない
        """
        qs = visible_students_qs(self.classroom_admin1)
        self.assertIn(self.student1, qs) # 組織1・組織1
        self.assertIn(self.student_actor1, qs)  # 組織1・教室1
        self.assertNotIn(self.student_actor1_2, qs)  #組織1・教室2
        self.assertNotIn(self.student_actor2, qs)  # 別テナント防御
        self.assertEqual(qs.count(), 2)  # 過剰に取得していないか
    
    def test_same_tenant_teacher_can_see_students(self):
        """
        教師は自身の担当している生徒は見れるが、そうでない生徒は同じ教室・組織であろうと見られない
        """
        qs = visible_students_qs(self.teacher1)
        self.assertIn(self.student1, qs)
        self.assertNotIn(self.student_actor1, qs)
        self.assertNotIn(self.student_actor1_2, qs)
        self.assertNotIn(self.student_actor2, qs)
        self.assertEqual(qs.count(), 1)

    def test_same_tenant_student_cannot_see_students(self):
        """
        生徒は自身も含め、まったく情報を見ることができない
        """
        qs = visible_students_qs(self.student1)
        self.assertNotIn(self.student1, qs)
        self.assertNotIn(self.student_actor1, qs)
        self.assertNotIn(self.student_actor1_2, qs)
        self.assertNotIn(self.student_actor2, qs)
        self.assertEqual(qs.count(), 0)

    def test_anonymous_user_cannot_see_student(self):
        """
        未ログインのユーザーは何も取得できない
        """
        qs = visible_students_qs(AnonymousUser())
        self.assertEqual(qs.count(), 0)

    def test_org_admin_cannot_see_inactive_student(self):
        """
        たとえ組織に所属している生徒でも非アクティブな生徒は見えない
        """
        self.student1.is_active = False
        self.student1.save()
        qs = visible_students_qs(self.org_admin1)
        self.assertNotIn(self.student1, qs)
        self.assertEqual(qs.count(), 2)
    
    def test_user_with_missing_role_object_cannot_see_students(self):
        """
        ロールオブジェクトが取得できないユーザーに関しては何も返さない
        """
        self.org_admin1.get_role_object = Mock(return_value=None)
        qs = visible_students_qs(self.org_admin1)
        self.assertEqual(qs.count(), 0)

    def test_teacher_without_assigned_students_cannot_see_students(self):
        """
        担当生徒がいない講師は何も取得できない
        """
        qs = visible_students_qs(self.teacher1_2)
        self.assertEqual(qs.count(), 0)

    def test_other_classroom_admin_can_only_see_own_classroom_students(self):
        """
        異なる教室の管理者は、自身の教室の生徒しか見えない
        """
        qs = visible_students_qs(self.classroom_admin1_2)
        self.assertIn(self.student_actor1_2, qs)
        self.assertNotIn(self.student1, qs)
        self.assertNotIn(self.student_actor1, qs)
        self.assertNotIn(self.student_actor2, qs)
        self.assertEqual(qs.count(), 1)

    def test_classroom_admin_cannot_see_inactive_student(self):
        """
        教室管理者も非アクティブな生徒は見えない
        """
        self.student1.is_active = False
        self.student1.save()
        qs = visible_students_qs(self.classroom_admin1)
        self.assertNotIn(self.student1, qs)
        self.assertEqual(qs.count(), 1)

    def test_teacher_cannot_see_inactive_assigned_student(self):
        """
        担任も非アクティブな生徒は見えない
        """
        self.student1.is_active = False
        self.student1.save()
        qs = visible_students_qs(self.teacher1)
        self.assertNotIn(self.student1, qs)
        self.assertEqual(qs.count(), 0)

    def test_classroom_admin_can_see_student_belonging_to_multiple_classrooms_without_duplicates(self):
        """
        複数の教室に所属する生徒を重複なしで正しくカウントできている
        """
        self.student1.classrooms.add(self.classroom1_2)
        qs = visible_students_qs(self.classroom_admin1)
        self.assertIn(self.student1, qs)
        self.assertEqual(qs.filter(pk=self.student1.pk).count(), 1)
        self.assertEqual(qs.count(), 2)
