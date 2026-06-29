from django.test import TestCase
from django.shortcuts import reverse
import uuid
from unittest.mock import patch, Mock
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import AnonymousUser
from django.http import Http404


from accounts.models import (
    Student,
    Teacher,
    ClassroomAdministrator,
    OrganizationAdministrator,
    Classroom,
    Organization
)
from study_reminder.utils.student_access_check import student_access_check


class StudentAccessCheck(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="org1")
        cls.org1_admin = OrganizationAdministrator.objects.create_user(
            username="org1_admin",
            email="org1_admin@example.com",
            password="pass123456"
        )
        cls.org1_admin.organizations.add(cls.org1)

        cls.class1_1 = Classroom.objects.create(name="class1_1", organization=cls.org1)
        cls.class1_1_admin = ClassroomAdministrator.objects.create_user(
            username="class1_1_admin",
            email="class1_1_admin@example.com",
            password="pass123456",
            organization=cls.org1
        )
        cls.class1_1_admin.classrooms.add(cls.class1_1)
        cls.class1_1_teacher = Teacher.objects.create_user(
            username="class1_1_teacher",
            email="class1_1_teacher@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.class1_1_teacher.classrooms.add(cls.class1_1)

        cls.class1_1_active_student = Student.objects.create_user(
            username="class1_1_active_student",
            email="class1_1_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_1_active_student"
        )
        cls.class1_1_active_student.classrooms.add(cls.class1_1)
        cls.class1_1_active_student.teachers.add(cls.class1_1_teacher)

        cls.class1_1_inactive_student = Student.objects.create_user(
            username="class1_1_inactive_student",
            email="class1_1_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_1_inactive_student"
        )
        cls.class1_1_inactive_student.classrooms.add(cls.class1_1)
        cls.class1_1_inactive_student.teachers.add(cls.class1_1_teacher)

        cls.class1_1_inactive_student_without_teacher = Student.objects.create_user(
            username="class1_1_inactive_student_without_teacher",
            email="class1_1_inactive_student_without_teacher@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_1_inactive_student_without_teacher"
        )
        cls.class1_1_inactive_student_without_teacher.classrooms.add(cls.class1_1)

        cls.class1_2 = Classroom.objects.create(name="class1_2", organization=cls.org1)
        cls.class1_2_admin = ClassroomAdministrator.objects.create_user(
            username="class1_2_admin",
            email="class1_2_admin@example.com",
            password="pass123456",
            organization=cls.org1,
        )
        cls.class1_2_admin.classrooms.add(cls.class1_2)
        cls.class1_2_active_student = Student.objects.create_user(
            username="class1_2_active_student",
            email="class1_2_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_2_active_student"
        )
        cls.class1_2_active_student.classrooms.add(cls.class1_2)
        cls.class1_2_inactive_student = Student.objects.create_user(
            username="class1_2_inactive_student",
            email="class1_2_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_2_inactive_student"
        )
        cls.class1_2_inactive_student.classrooms.add(cls.class1_2)

        cls.class1_not_active_student = Student.objects.create_user(
            username="class1_not_active_student",
            email="class1_not_active_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=True,
            line_user_id="line_id_class1_not_active_student"
        )
        cls.class1_not_inactive_student = Student.objects.create_user(
            username="class1_not_inactive_student",
            email="class1_not_inactive_student@example.com",
            password="pass123456",
            organization=cls.org1,
            is_active=False,
            line_user_id="line_id_class1_not_inactive_student"
        )


        cls.org2 = Organization.objects.create(name="org2")
        cls.class2 = Classroom.objects.create(name="class2", organization=cls.org2)
        cls.class2_active_student = Student.objects.create_user(
            username="class2_active_student",
            email="class2_active_student@example.com",
            password="pass123456",
            organization=cls.org2,
            is_active=True,
            line_user_id="line_id_class2_active_student"
        )
        cls.class2_active_student.classrooms.add(cls.class2)

        cls.class2_inactive_student = Student.objects.create_user(
            username="class2_inactive_student",
            email="class2_inactive_student@example.com",
            password="pass123456",
            organization=cls.org2,
            is_active=False,
            line_user_id="line_id_class2_inactive_student"
        )
        cls.class2_inactive_student.classrooms.add(cls.class2)
    
        cls.url_to_class1_1 = reverse(
            "organization_admin:student_reactivate",
            kwargs={"classroom_id": cls.class1_1.id},
        )

    def test_org_admin_can_access_own_and_active_student(self):
        """
        組織管理者は自身の組織かつアクティブな生徒を取得可能
        """
        org_admin = self.org1_admin
        target_student = self.class1_1_active_student
        student = student_access_check(org_admin, target_student.id)
        self.assertEqual(target_student, student)
    
    def test_classroom_admin_can_access_own_and_active_student(self):
        """
        教室管理者は自身の担当教室所属かつアクティブな生徒を取得可能
        """
        class_admin = self.class1_1_admin
        target_student = self.class1_1_active_student
        student = student_access_check(class_admin, target_student.id)
        self.assertEqual(target_student, student)

    def test_teacher_can_access_assigned_and_active_student(self):
        """
        講師は担当かつアクティブな生徒を取得可能
        """
        teacher = self.class1_1_teacher
        target_student = self.class1_1_active_student
        student = student_access_check(teacher, target_student.id)
        self.assertEqual(target_student, student)
    
    def test_student_can_access_only_themselves(self):
        """
        生徒は自分自身のみアクセス可能
        """
        student_self = self.class1_1_active_student
        student = student_access_check(student_self, student_self.id)
        self.assertEqual(student_self, student)

    def test_org_admin_cannot_access_another_organization_student(self):
        """
        組織管理者は別の組織の生徒にはアクセスできない
        """
        org_admin = self.org1_admin
        another_org_student = self.class2_active_student
        with self.assertRaises(PermissionDenied):
            student = student_access_check(org_admin, another_org_student.id)
    
    def test_classroom_admin_cannot_access_another_classroom_student(self):
        """
        教室管理者は別教室の組織の生徒にはアクセスできない
        """
        class_admin = self.class1_1_admin
        another_classroom_student = self.class1_2_active_student
        with self.assertRaises(PermissionDenied):
            student = student_access_check(class_admin, another_classroom_student.id)
    
    def test_teacher_cannot_access_unassigned_student(self):
        """
        講師は担当でない生徒にはアクセスできない
        """
        teacher = self.class1_1_teacher
        unassigned_student = self.class1_2_active_student
        with self.assertRaises(PermissionDenied):
            student = student_access_check(teacher, unassigned_student.id)

    def test_student_cannot_access_any_students_except_themselves(self):
        """
        生徒は自分自身以外の生徒にアクセスできない
        """
        student = self.class1_1_active_student
        another_student = self.class1_2_active_student
        with self.assertRaises(PermissionDenied):
            student = student_access_check(student, another_student.id)

    def test_anonymous_user_cannot_access(self):
        """
        未ログインユーザーはアクセス不可
        """
        anonymous_user = AnonymousUser()
        student = self.class1_1_active_student
        with self.assertRaises(PermissionDenied):
            student = student_access_check(anonymous_user, student.id)
    
    def test_none_role_object_cause_403(self):
        """
        ロールオブジェクトがNoneだとアクセス不可
        """
        org_admin = self.org1_admin
        org_admin.get_role_object = Mock(return_value=None)
        student = self.class1_1_active_student
        with self.assertRaises(PermissionDenied):
            student = student_access_check(org_admin, student.id)
    
    def test_lack_of_student_id_cause_403(self):
        """
        生徒IDが指定されていないとアクセス不可
        """
        org_admin = self.org1_admin
        with self.assertRaises(PermissionDenied):
            student = student_access_check(org_admin, "")
    
    def test_inactive_student_cannot_be_accessed(self):
        """
        非アクティブな生徒はアクセスされない
        """
        org_admin = self.org1_admin
        inactive_student = self.class1_1_inactive_student
        with self.assertRaises(Http404):
            student = student_access_check(org_admin, inactive_student.id)

    def test_access_to_non_existent_student_raise_404(self):
        """
        存在しない生徒はアクセスされない
        """
        org_admin = self.org1_admin
        non_existent_student_id = uuid.uuid4()
        with self.assertRaises(Http404):
            student = student_access_check(org_admin, non_existent_student_id)

    def test_student_role_with_non_student_role_object_cause_403(self):
        """
        studentロールなのに role_obj が Student でなければアクセス不可
        """
        student_user = self.class1_1_active_student
        student_user.get_role_object = Mock(return_value=self.class1_1_teacher)  # get_role_objectが講師オブジェクトを返すように

        with self.assertRaises(PermissionDenied):
            student_access_check(student_user, student_user.id)

    def test_unexpected_role_cause_403(self):
        """
        想定外ロールはアクセス不可
        """
        user = Mock()
        user.is_authenticated = True
        user.id = uuid.uuid4()
        user.role = "unexpected_role"
        user.get_role_object = Mock(return_value=Mock())

        with self.assertRaises(PermissionDenied):
            student_access_check(user, self.class1_1_active_student.id)

    def test_none_student_id_cause_403(self):
        """
        生徒IDがNoneでもアクセス不可
        """
        org_admin = self.org1_admin

        with self.assertRaises(PermissionDenied):
            student_access_check(org_admin, None)
