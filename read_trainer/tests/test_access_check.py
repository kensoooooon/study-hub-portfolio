"""
access_checkに含まれるメソッドのテストを実施
"""

from django.test import TestCase
from unittest.mock import patch
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import AnonymousUser
from django.http import Http404

import uuid

from accounts.models import (
    OrganizationAdministrator,
    Organization,
    ClassroomAdministrator,
    Classroom,
    Teacher,
    Student
)
from read_trainer.models import ReadingPassage

from read_trainer.access_check.student_access_check import get_role_object_or_403, ensure_can_access_student, student_access_check
from read_trainer.access_check.passage_access_check import passage_access_check, parse_passage_id_or_404


class StudentAccessCheckTest(TestCase):
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

        cls.org2_admin = OrganizationAdministrator.objects.create_user(
            username="org2_admin",
            email="org2_admin@example.com",
            password="pass123456",
        )
        cls.org2_admin.organizations.add(cls.org2)

        cls.class2_teacher = Teacher.objects.create_user(
            username="class2_teacher",
            email="class2_teacher@example.com",
            password="pass123456",
            organization=cls.org2,
        )
        cls.class2_teacher.classrooms.add(cls.class2)

        # 講師は、同一組織内であれば「別教室の生徒」でも担当していればアクセスできる
        cls.class1_2_active_student.teachers.add(cls.class1_1_teacher)

        # データ上は担当関係があっても、異なる組織の生徒はアクセス不可であることを確認するため
        cls.class2_active_student.teachers.add(cls.class1_1_teacher)
    
    
    def login_as_classroom_admin(self):
        ok = self.client.login(email="class1_1_admin@example.com", password="pass123456")
        self.assertTrue(ok)

    def login_as_org_admin(self):
        ok = self.client.login(email="org1_admin@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_as_teacher(self):
        ok = self.client.login(email="class1_1_teacher@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def login_as_student(self):
        ok = self.client.login(email="class1_1_active_student@example.com", password="pass123456")
        self.assertTrue(ok)
    
    def test_get_role_object_or_403_for_anonymous_cause_403(self):
        """
        未ログインユーザーは403
        """
        with self.assertRaises(PermissionDenied):
            role_object = get_role_object_or_403(AnonymousUser())

    @patch("accounts.models.BaseUser.get_role_object")
    def test_get_role_object_or_403_with_none_cause_403(self, mock_role_object):
        """
        get_role_objectでNoneが返ってくる場合は403判定になる
        """
        mock_role_object.return_value = None
        with self.assertRaises(PermissionDenied):
            role_object = get_role_object_or_403(self.org1_admin)
    
    def test_get_role_object_or_403_returns_org_admin_object(self):
        """
        組織管理者からはOrganizationAdministratorのオブジェクトが返ってくる
        """
        role_object = get_role_object_or_403(self.org1_admin)
        self.assertIsInstance(role_object, OrganizationAdministrator)
    
    def test_get_role_object_or_403_returns_classroom_admin_object(self):
        """
        教室管理者からはClassroomAdministratorのオブジェクトが返ってくる
        """
        role_object = get_role_object_or_403(self.class1_1_admin)
        self.assertIsInstance(role_object, ClassroomAdministrator)
    
    def test_get_role_object_or_403_returns_teacher_object(self):
        """
        講師からはTeacherのオブジェクトが返ってくる
        """
        role_object = get_role_object_or_403(self.class1_1_teacher)
        self.assertIsInstance(role_object, Teacher)
    
    def test_get_role_object_or_403_returns_student_object(self):
        """
        生徒からはStudentのオブジェクトが返ってくる
        """
        role_object = get_role_object_or_403(self.class1_1_active_student)
        self.assertIsInstance(role_object, Student)
    
    def test_get_role_object_or_403_returns_student_object_for_inactive_student(self):
        """
        非アクティブ生徒からもStudentのオブジェクトが返ってくる
        """
        role_object = get_role_object_or_403(self.class1_1_inactive_student)
        self.assertIsInstance(role_object, Student)

    @patch("accounts.models.BaseUser.get_role_object")
    def test_get_role_object_or_403_when_get_role_object_raises_exception(self, mock_get_role_object):
        """
        ロールオブジェクト取得中に例外が発生した場合は403
        """
        mock_get_role_object.side_effect = Exception("broken role relation")

        with self.assertRaises(PermissionDenied):
            get_role_object_or_403(self.org1_admin)

    def test_ensure_can_access_student_raise_403_for_anonymous_user(self):
        """
        未ログインユーザーは403
        """
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(AnonymousUser(), self.class1_1_active_student)

    def test_ensure_can_access_student_confirms_access_for_org_admin_with_right_student(self):
        """
        組織管理者が自身の管理している組織の生徒にアクセスすれば特に例外は起きない
        """
        result = ensure_can_access_student(self.org1_admin, self.class1_1_active_student)
        self.assertIsNone(result)

    
    def test_ensure_can_access_student_raise_403_when_student_argument_is_not_student_object(self):
        """
        studentではないオブジェクトが渡された場合は403
        """
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(self.org1_admin, self.class1_1_teacher)  # 講師が渡された
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(self.org1_admin, self.class1_1_active_student.id)  # 生徒ではなくIDが渡されてしまった

    def test_ensure_can_access_student_raise_404_for_inactive_student(self):
        """
        対象studentがアクティブでない場合は404
        """
        with self.assertRaises(Http404):
            ensure_can_access_student(self.org1_admin, self.class1_1_inactive_student)

    def test_ensure_can_access_student_raise_403_for_org_admin_with_other_org_student(self):
        """
        組織管理者は自身の組織に所属していない生徒へアクセス不可
        """
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(self.org1_admin, self.class2_active_student)

    def test_ensure_can_access_student_raise_404_for_org_admin_with_inactive_student_in_own_org(self):
        """
        組織管理者は自身の組織に所属していても、非アクティブ生徒へはアクセス不可
        """
        with self.assertRaises(Http404):
            ensure_can_access_student(self.org1_admin, self.class1_1_inactive_student)

    def test_ensure_can_access_student_confirms_access_for_classroom_admin_with_student_in_own_classroom(self):
        """
        教室管理者は自身の教室に所属しているアクティブ生徒へアクセス可能
        """
        result = ensure_can_access_student(
            self.class1_1_admin,
            self.class1_1_active_student,
        )

        self.assertIsNone(result)

    def test_ensure_can_access_student_raise_403_for_classroom_admin_with_student_in_other_classroom_same_org(self):
        """
        教室管理者は同じ組織でも、自身の管理している教室には所属していない生徒へはアクセス不可
        """
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(
                self.class1_1_admin,
                self.class1_2_active_student,
            )

    def test_ensure_can_access_student_raise_404_for_classroom_admin_with_inactive_student_in_own_classroom(self):
        """
        教室管理者は自身の教室に所属していても、非アクティブ生徒へはアクセス不可
        """
        with self.assertRaises(Http404):
            ensure_can_access_student(
                self.class1_1_admin,
                self.class1_1_inactive_student,
            )

    def test_ensure_can_access_student_raise_403_for_classroom_admin_with_other_org_student(self):
        """
        教室管理者は異なる組織の生徒へアクセス不可
        """
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(
                self.class1_1_admin,
                self.class2_active_student,
            )

    def test_ensure_can_access_student_confirms_access_for_teacher_with_assigned_active_student(self):
        """
        講師は自身の担当しているアクティブ生徒にアクセス可
        """
        result = ensure_can_access_student(
            self.class1_1_teacher,
            self.class1_1_active_student,
        )

        self.assertIsNone(result)

    def test_ensure_can_access_student_raise_403_for_teacher_with_unassigned_student_in_same_classroom(self):
        """
        講師は同じ教室でも自身の担当していない生徒にアクセス不可
        """
        # 同じ教室に所属するが、class1_1_teacher には担当させていない生徒を作る
        unassigned_student = Student.objects.create_user(
            username="class1_1_unassigned_student",
            email="class1_1_unassigned_student@example.com",
            password="pass123456",
            organization=self.org1,
            is_active=True,
            line_user_id="line_id_class1_1_unassigned_student",
        )
        unassigned_student.classrooms.add(self.class1_1)

        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(
                self.class1_1_teacher,
                unassigned_student,
            )

    def test_ensure_can_access_student_confirms_access_for_teacher_with_assigned_student_in_other_classroom_same_org(self):
        """
        講師は異なる教室でも担当していればアクセス可
        """
        result = ensure_can_access_student(
            self.class1_1_teacher,
            self.class1_2_active_student,
        )

        self.assertIsNone(result)

    def test_ensure_can_access_student_raise_403_for_teacher_with_student_in_other_org(self):
        """
        講師は異なる組織の生徒にアクセス不可
        """
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(
                self.class1_1_teacher,
                self.class2_active_student,
            )

    def test_ensure_can_access_student_raise_404_for_teacher_with_assigned_inactive_student(self):
        """
        講師はたとえ担任していても、非アクティブ生徒へはアクセス不可
        """
        with self.assertRaises(Http404):
            ensure_can_access_student(
                self.class1_1_teacher,
                self.class1_1_inactive_student,
            )

    def test_ensure_can_access_student_confirms_access_for_student_self(self):
        """
        生徒は自分自身にアクセス可能
        """
        result = ensure_can_access_student(
            self.class1_1_active_student,
            self.class1_1_active_student,
        )

        self.assertIsNone(result)

    def test_ensure_can_access_student_raise_404_for_inactive_student_user_self_access(self):
        """
        非アクティブ生徒が自分自身へアクセスしようとした場合は404
        """
        with self.assertRaises(Http404):
            ensure_can_access_student(
                self.class1_1_inactive_student,
                self.class1_1_inactive_student,
            )

    def test_ensure_can_access_student_raise_403_for_student_with_other_student_same_classroom(self):
        """
        生徒は同じ教室の他生徒へアクセス不可
        """
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(
                self.class1_1_active_student,
                self.class1_2_active_student,
            )

    def test_ensure_can_access_student_raise_403_for_student_with_other_student_other_org(self):
        """
        生徒は組織、教室の有無に関わらず、自身以外にアクセス不可
        """
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(
                self.class1_1_active_student,
                self.class2_active_student,
            )

    @patch("read_trainer.access_check.student_access_check.get_role_object_or_403")
    def test_ensure_can_access_student_raise_403_when_admin_role_object_has_no_can_manage_student(
        self,
        mock_get_role_object,
    ):
        """
        ロールオブジェクトは取得できたが、can_manage_studentを持たないものだった場合は403
        """
        class DummyRoleObject:
            pass

        mock_get_role_object.return_value = DummyRoleObject()

        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(self.org1_admin, self.class1_1_active_student)

    @patch("read_trainer.access_check.student_access_check.get_role_object_or_403")
    def test_ensure_can_access_student_raise_403_when_student_role_object_is_not_student(
        self,
        mock_get_role_object,
    ):
        """
        生徒ロールなのに生徒ロールオブジェクトが得られていないときは403
        """
        mock_get_role_object.return_value = self.org1_admin

        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(
                self.class1_1_active_student,
                self.class1_1_active_student,
            )
    
    @patch("read_trainer.access_check.student_access_check.get_role_object_or_403")
    def test_ensure_can_access_student_raise_403_for_unexpected_role(
        self,
        mock_get_role_object,
    ):
        """
        role_obj は取得できたが、role が想定外の場合は403
        """
        class DummyRoleObject:
            pass

        mock_get_role_object.return_value = DummyRoleObject()

        user = OrganizationAdministrator.objects.create_user(
            username="unexpected_role_user",
            email="unexpected_role_user@example.com",
            password="pass123456",
        )
        user.role = "unexpected_role"

        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(user, self.class1_1_active_student)

    def test_student_access_check_raise_403_when_student_id_missing(self):
        """
        生徒IDが指定されていない場合は403
        """
        with self.assertRaises(PermissionDenied):
            student_access_check(self.org1_admin, None)

    def test_student_access_check_raise_403_when_student_id_is_empty_string(self):
        """
        生徒IDが空文字の場合は403
        """
        with self.assertRaises(PermissionDenied):
            student_access_check(self.org1_admin, "")
    
    def test_student_access_check_raise_404_when_student_id_does_not_exist(self):
        """
        存在しない生徒IDを指定した場合は404
        """
        non_existent_id = uuid.uuid4()
        with self.assertRaises(Http404):
            student_access_check(self.org1_admin, non_existent_id)

    def test_student_access_check_with_invalid_uuid_string(self):
        """
        UUID形式でないstudent_idが渡された場合は403
        """
        with self.assertRaises(PermissionDenied):
            student_access_check(self.org1_admin, "not-a-uuid")

    def test_student_access_check_raise_404_when_student_is_inactive(self):
        """
        対象生徒が非アクティブの場合は404
        """
        with self.assertRaises(Http404):
            student_access_check(self.org1_admin, self.class1_1_inactive_student.id)

    def test_student_access_check_returns_student_when_access_allowed(self):
        """
        組織管理者は自組織に所属する生徒へアクセス可能
        """
        student = student_access_check(self.org1_admin, self.class1_1_active_student.id)
        self.assertEqual(student, self.class1_1_active_student)

    def test_student_access_check_returns_student_for_org_admin_with_other_classroom_same_org_student(self):
        """
        組織管理者は同一組織内の別教室生徒にもアクセス可能
        """
        student = student_access_check(
            self.org1_admin,
            self.class1_2_active_student.id,
        )

        self.assertEqual(student, self.class1_2_active_student)

    def test_student_access_check_raise_403_when_access_denied(self):
        """
        組織管理者は異なる組織に所属する生徒へアクセス不可
        """
        with self.assertRaises(PermissionDenied):
            student = student_access_check(self.org1_admin, self.class2_active_student.id)
    
    def test_student_access_check_raise_403_for_classroom_admin_with_other_org_student(self):
        """
        教室管理者は異なる組織の生徒IDを指定してもアクセス不可
        """
        with self.assertRaises(PermissionDenied):
            student_access_check(
                self.class1_1_admin,
                self.class2_active_student.id,
            )

    def test_ensure_can_access_student_confirms_access_for_classroom_admin_with_student_in_their_other_classroom(self):
        """
        class1_2管理者はclass1_2所属の生徒へアクセス可能
        """
        result = ensure_can_access_student(
            self.class1_2_admin,
            self.class1_2_active_student,
        )

        self.assertIsNone(result)

    def test_student_access_check_passes_another_classroom_in_same_org_student(self):
        """
        講師は同一組織かつ異なる教室のとき、担当生徒であればアクセス可能
        """
        student = student_access_check(self.class1_1_teacher, self.class1_2_active_student.id)
        self.assertEqual(student, self.class1_2_active_student)
    
    def test_student_access_check_raise_403_when_org_is_not_the_same(self):
        """
        講師は担当関係にあっても、異なる組織の生徒にはアクセス不可
        """
        with self.assertRaises(PermissionDenied):
            student = student_access_check(self.class1_1_teacher, self.class2_active_student.id)

    def test_student_access_check_raise_404_when_student_user_targets_inactive_student(self):
        """
        生徒ユーザーが非アクティブ生徒IDを指定した場合は404
        """
        with self.assertRaises(Http404):
            student = student_access_check(
                self.class1_1_active_student,
                self.class1_1_inactive_student.id,
            )
    
    # inspired by claude
    def test_not_id_but_student_raise_403(self):
        """
        IDではなく、生徒オブジェクトそのものを対象とした場合403
        """
        with self.assertRaises(PermissionDenied):
            student = student_access_check(self.org1_admin, self.class1_1_active_student)
    
    def test_org_admin_can_access_student_not_in_classroom_but_in_org(self):
        """
        組織管理者は教室に所属していなくても、自身の組織に所属している生徒にはアクセス可能
        """
        student_only_in_org = Student.objects.create_user(
            username="not classroom but org",
            line_user_id="not_classroom_but_org_line_user_id",
            organization=self.org1
        )
        student = student_access_check(self.org1_admin, student_only_in_org.id)
        self.assertEqual(student.id, student_only_in_org.id)
    
    def test_org_admin_can_access_student_not_in_org_but_in_classroom(self):
        """
        組織管理者は組織に所属していなくても、自身の組織に所属している教室に所属しいれば生徒にアクセス可能
        """
        student_only_in_classroom = Student.objects.create_user(
            username="not org but classroom",
            line_user_id="not_org_but_classroom_line_user_id",
        )
        student_only_in_classroom.classrooms.add(self.class1_1)
        student = student_access_check(self.org1_admin, student_only_in_classroom.id)
        self.assertEqual(student.id, student_only_in_classroom.id)
    

    # claude
    def test_student_cannot_access_another_student_in_same_org(self):
        """
        生徒は同じ組織であっても自分自身以外の生徒は403
        """
        with self.assertRaises(PermissionDenied):
            student = student_access_check(self.class1_1_active_student, self.class1_2_active_student.id)
    
    def test_student_can_access_self(self):
        """
        生徒は自分自身にアクセス可能
        """
        student = student_access_check(self.class1_1_active_student, self.class1_1_active_student.id)
        self.assertEqual(student.id, self.class1_1_active_student.id)

    def test_classroom_admin_can_access_students_in_classroom(self):
        """
        教室管理者は自身の教室に所属している生徒にアクセス可能
        """
        student = student_access_check(self.class1_1_admin, self.class1_1_active_student.id)
        self.assertEqual(student.id, self.class1_1_active_student.id)

    def test_inactive_student_cannot_access_self(self):
        """
        非アクティブ生徒は自分自身にアクセス不可
        """
        with self.assertRaises(Http404):
            student = student_access_check(self.class1_1_inactive_student, self.class1_1_inactive_student.id)
    
    def test_teacher_can_access_student_in_same_classroom(self):
        """
        講師は同じ教室の担当生徒にアクセス可能
        """
        student = student_access_check(self.class1_1_teacher, self.class1_1_active_student.id)
        self.assertEqual(student.id, self.class1_1_active_student.id)


class ReadingPassageCheckTest(TestCase):
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

        cls.org2_admin = OrganizationAdministrator.objects.create_user(
            username="org2_admin",
            email="org2_admin@example.com",
            password="pass123456",
        )
        cls.org2_admin.organizations.add(cls.org2)

        cls.class2_teacher = Teacher.objects.create_user(
            username="class2_teacher",
            email="class2_teacher@example.com",
            password="pass123456",
            organization=cls.org2,
        )
        cls.class2_teacher.classrooms.add(cls.class2)

        # 講師は、同一組織内であれば「別教室の生徒」でも担当していればアクセスできる
        cls.class1_2_active_student.teachers.add(cls.class1_1_teacher)

        # データ上は担当関係があっても、異なる組織の生徒はアクセス不可であることを確認するため
        cls.class2_active_student.teachers.add(cls.class1_1_teacher)

        cls.class1_1_active_student_textbook_passage = ReadingPassage.objects.create(
            title="sample passage title",
            content="this is sample passage content.",
            created_by=cls.class1_1_active_student,
            source_type="textbook",
        )

        cls.class1_1_active_student_eiken_passage = ReadingPassage.objects.create(
            title="sample passage title",
            content="this is sample passage content.",
            created_by=cls.class1_1_active_student,
            source_type="eiken",
        )

        cls.class1_2_active_student_eiken_passage = ReadingPassage.objects.create(
            title="sample passage title",
            content="this is sample passage content.",
            created_by=cls.class1_2_active_student,
            source_type="eiken",
        )

        cls.class2_active_student_textbook_passage = ReadingPassage.objects.create(
            title="sample passage title",
            content="this is sample passage content.",
            created_by=cls.class2_active_student,
            source_type="textbook",
        )
    
    # 境界系

    def test_org_admin_can_access_passage_with_student_belonging_with_org(self):
        """
        組織管理者は自身の管理組織の生徒が作った長文にアクセス可能
        """
        passage = passage_access_check(
            self.org1_admin,
            self.class1_1_active_student_textbook_passage.id,
            source_type="textbook",
            expected_student_id=self.class1_1_active_student.id
        )
        self.assertEqual(passage.id, self.class1_1_active_student_textbook_passage.id)

    def test_org_admin_cannot_access_passage_with_another_org_student(self):
        """
        組織管理者は他の組織の生徒が作成した長文へのアクセス不可
        """
        with self.assertRaises(Http404):
            passage = passage_access_check(
                self.org1_admin,
                self.class2_active_student_textbook_passage.id,
            )
    
    def test_classroom_admin_can_access_passage_with_student_belonging_with_classroom(self):
        """
        教室管理者は自身が管理している教室の生徒が作成した長文にアクセス可能
        """
        passage = passage_access_check(
            self.class1_1_admin,
            self.class1_1_active_student_eiken_passage.id,
            source_type="eiken",
            expected_student_id=self.class1_1_active_student.id
        )
        self.assertEqual(passage.id, self.class1_1_active_student_eiken_passage.id)
    
    def test_classroom_admin_cannot_access_passage_with_another_org_student(self):
        """
        教室管理者は他の組織の生徒が作った長文へのアクセス不可
        """
        with self.assertRaises(Http404):
            passage = passage_access_check(
                self.class1_1_admin,
                self.class2_active_student_textbook_passage.id,
            )
    def test_classroom_admin_cannot_access_passage_with_another_classroom_student(self):
        """
        教室管理者は他の教室の生徒の長文にアクセス不可
        """
        with self.assertRaises(Http404):
            passage = passage_access_check(
                self.class1_1_admin,
                self.class1_2_active_student_eiken_passage.id,
            )
    
    def test_teacher_can_access_passage_with_assigned_student(self):
        """
        講師は担当している生徒の作成した長文にアクセス可
        """
        passage = passage_access_check(
            self.class1_1_teacher,
            self.class1_1_active_student_textbook_passage.id,
        )
        self.assertEqual(passage.id, self.class1_1_active_student_textbook_passage.id)
    
    def test_teacher_can_access_passage_with_assigned_student_in_another_classroom(self):
        """
        講師は担当している生徒が他教室であっても長文にアクセス可能
        """
        passage = passage_access_check(
            self.class1_1_teacher,
            self.class1_2_active_student_eiken_passage.id,
        )
        self.assertEqual(passage.id, self.class1_2_active_student_eiken_passage.id)
    
    def test_teacher_cannot_access_passage_with_assigned_student_in_another_org(self):
        """
        講師はたとえ担当していても、他組織の生徒の長文にはアクセス不可
        """
        with self.assertRaises(Http404):
            passage = passage_access_check(
                self.class1_1_teacher,
                self.class2_active_student_textbook_passage.id
            )
    
    def test_student_can_access_their_passage(self):
        """
        生徒は自分自身の作成した長文にアクセス可能
        """
        passage = passage_access_check(
            self.class1_1_active_student,
            self.class1_1_active_student_eiken_passage.id,
        )
        self.assertEqual(passage.id, self.class1_1_active_student_eiken_passage.id)
    
    def test_student_cannot_access_any_other_passage(self):
        """
        生徒は自分自身が作成した長文以外は全てアクセス不可
        """
        passage_ids = [
            self.class1_2_active_student_eiken_passage.id,
            self.class2_active_student_textbook_passage.id,
        ]
        for passage_id in passage_ids:
            with self.assertRaises(Http404):
                passage = passage_access_check(
                    self.class1_1_active_student,
                    passage_id,
                )
    
    # 設定ミス系
    def test_all_users_cannot_access_passage_when_source_type_is_wrong(self):
        """
        全てのユーザーは本来アクセスできるはずの長文でも、タイプの指定が間違っていればアクセス不可
        """
        users = [
            self.org1_admin,
            self.class1_1_admin,
            self.class1_1_teacher,
            self.class1_1_active_student
        ]
        for user in users:
            with self.assertRaises(Http404):
                passage = passage_access_check(
                    user,
                    self.class1_1_active_student_eiken_passage.id,
                    source_type="textbook"
                )

    def test_all_users_cannot_access_passage_when_expected_student_id_is_wrong(self):
        """
        全てのユーザーはアクセス可能であっても、期待される生徒IDの指定が間違っていればアクセス不可
        """
        users = [
            self.org1_admin,
            self.class1_1_admin,
            self.class1_1_teacher,
            self.class1_1_active_student
        ]
        for user in users:
            with self.assertRaises(Http404):
                passage = passage_access_check(
                    user,
                    self.class1_1_active_student_eiken_passage.id,
                    expected_student_id=self.class1_2_active_student.id
                )
    
    def test_all_users_cannot_access_without_passage_id(self):
        """
        長文のIDが指定されていないときは404
        """
        users = [
            self.org1_admin,
            self.class1_1_admin,
            self.class1_1_teacher,
            self.class1_1_active_student
        ]
        for user in users:
            with self.assertRaises(Http404):
                passage = passage_access_check(user, "")

    
    def test_all_users_cannot_access_without_not_int_passage_id(self):
        """
        長文のIDが整数型として解釈できない場合は404
        """
        users = [
            self.org1_admin,
            self.class1_1_admin,
            self.class1_1_teacher,
            self.class1_1_active_student
        ]
        for user in users:
            with self.assertRaises(Http404):
                passage = passage_access_check(user, "abc")

    def test_all_user_cannot_access_when_passage_id_is_passage_self(self):
        """
        長文のIDではなく、長文そのものが渡されたら404
        """
        users = [
            self.org1_admin,
            self.class1_1_admin,
            self.class1_1_teacher,
            self.class1_1_active_student
        ]
        for user in users:
            with self.assertRaises(Http404):
                passage = passage_access_check(
                    user,
                    self.class1_1_active_student_eiken_passage,
                    source_type="eiken",
                    expected_student_id=self.class1_1_active_student.id
                    )
    
    def test_all_user_cannot_access_when_source_type_does_not_exist(self):
        """
        存在しないソースタイプを指定されると404
        """
        users = [
            self.org1_admin,
            self.class1_1_admin,
            self.class1_1_teacher,
            self.class1_1_active_student
        ]
        for user in users:
            with self.assertRaises(Http404):
                passage = passage_access_check(
                    user,
                    self.class1_1_active_student_textbook_passage.id,
                    source_type="unexpected type")

    def test_all_user_cannot_access_when_creator_does_not_exist(self):
        """
        作成者が存在しない長文は404
        """
        passage_without_student = ReadingPassage.objects.create(
            title="sample passage title",
            content="this is sample passage content.",
            source_type="eiken"
            )
        users = [
            self.org1_admin,
            self.class1_1_admin,
            self.class1_1_teacher,
            self.class1_1_active_student
        ]
        for user in users:
            with self.assertRaises(Http404):
                passage = passage_access_check(
                    user,
                    passage_without_student.id,
                    source_type="eiken",
                )

    def test_all_user_cannot_access_passage_with_inactive_studnt(self):
        """
        非アクティブ生徒が作成した長文はensure_can_access_studentにひっかかるので、たとえ権限内でも403
        """
        passage_with_inactive_student = ReadingPassage.objects.create(
            title="sample passage title",
            content="this is sample passage content.",
            created_by=self.class1_1_inactive_student,
            source_type="eiken",
        )
        users = [
            self.org1_admin,
            self.class1_1_admin,
            self.class1_1_teacher,
            self.class1_1_active_student
        ]
        for user in users:
            with self.assertRaises(Http404):
                passage = passage_access_check(
                    user,
                    passage_with_inactive_student.id,
                    source_type="eiken",
                )

    # ChatGPTによる追加
    def test_passage_access_check_passes_when_expected_student_id_is_same_uuid_string(self):
        """
        文字列で指定されても、生徒IDが一致して通過とみなされるか(冪等性)
        """
        passage = passage_access_check(
            self.org1_admin,
            self.class1_1_active_student_eiken_passage.id,
            expected_student_id=str(self.class1_1_active_student.id),
        )

        self.assertEqual(passage, self.class1_1_active_student_eiken_passage)

    def test_passage_access_check_raises_404_when_expected_student_id_mismatches_with_valid_id(self):
        with self.assertRaises(Http404):
            passage_access_check(
                self.org1_admin,
                self.class1_1_active_student_eiken_passage.id,
                expected_student_id=self.class1_2_active_student.id,
            )

    def test_teacher_cannot_access_unassigned_student_passage_in_same_org(self):
        """
        同じ組織、教室に所属していても、担当できなければアクセス不可
        """
        unassigned_student = Student.objects.create_user(
            username="unassigned_student",
            email="unassigned_student@example.com",
            password="pass123456",
            organization=self.org1,
            is_active=True,
            line_user_id="line_unassigned_student",
        )
        unassigned_student.classrooms.add(self.class1_1)

        passage = ReadingPassage.objects.create(
            title="unassigned",
            content="content",
            created_by=unassigned_student,
            source_type="textbook",
        )

        with self.assertRaises(Http404):
            passage_access_check(self.class1_1_teacher, passage.id)

    def test_student_cannot_access_same_classroom_other_student_passage(self):
        """
        生徒は同じ教室であっても長文にアクセス不可
        """
        other_passage = ReadingPassage.objects.create(
            title="other",
            content="content",
            created_by=self.class1_2_active_student,
            source_type="eiken",
        )

        with self.assertRaises(Http404):
            passage_access_check(
                self.class1_1_active_student,
                other_passage.id,
            )

    def test_passage_access_check_does_not_accept_zero(self):
        """
        取得時に長文0のidは弾かれる
        """
        with self.assertRaises(Http404):
            passage_access_check(self.org1_admin, 0)

    def test_passage_access_check_does_not_accept_negative_value(self):
        """
        負のidは弾かれる
        """
        with self.assertRaises(Http404):
            passage_access_check(self.org1_admin, -1)

    def test_passage_access_check_does_not_accept_decimal(self):
        """
        小数のidは弾かれる
        """
        with self.assertRaises(Http404):
            passage_access_check(self.org1_admin, "1.5")
    
    def test_anonymous_user_cannot_access_passage(self):
        """
        未ログインユーザーからのアクセスは404で処理される
        """
        with self.assertRaises(Http404):
            passage_access_check(
                AnonymousUser(),
                self.class1_1_active_student_textbook_passage.id,
            )

    def test_visible_to_for_teacher_excludes_other_org_even_if_assigned(self):
        """
        担当でも他の組織の生徒であれば可視範囲に含まれない
        """
        qs = ReadingPassage.objects.visible_to(self.class1_1_teacher)
        self.assertNotIn(self.class2_active_student_textbook_passage, qs)

    def test_parse_passage_id_or_404_raises_404_for_zero(self):
        """
        パース時に0は弾かれる
        """
        with self.assertRaises(Http404):
            parse_passage_id_or_404(self.org1_admin, 0)

    def test_parse_passage_id_or_404_raises_404_for_negative_integer(self):
        """
        パース時に負の数は弾かれる
        """
        with self.assertRaises(Http404):
            parse_passage_id_or_404(self.org1_admin, -1)

    def test_parse_passage_id_or_404_raises_404_for_float_like_string(self):
        """
        パース時に小数は弾かれる
        """
        with self.assertRaises(Http404):
            parse_passage_id_or_404(self.org1_admin, "1.5")

    # claude
    # # 追加すべきテスト例
    # passage_access_check(org1_admin, 99999)  # → Http404
    def test_non_existent_passage_id_raise_404(self):
        """
        存在しない長文IDは弾かれる
        """
        with self.assertRaises(Http404):
            passage = passage_access_check(self.org1_admin, 99999)
    
    def test_none_passage_id_raise_404(self):
        """
        長文IDがNoneだと弾かれる
        """
        with self.assertRaises(Http404):
            passage = passage_access_check(self.org1_admin, None)

    def test_passage_instead_of_passage_id_raise_404(self):
        """
        長文IDの代わりに長文そのものを渡すと弾かれる
        """
        with self.assertRaises(Http404):
            passage = passage_access_check(self.org1_admin, self.class1_1_active_student_eiken_passage)
