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
from listening_trainer.models import ListeningPassage

from listening_trainer.access_check.student_access_check import get_role_object_or_403, ensure_can_access_student, student_access_check
from listening_trainer.access_check.passage_access_check import passage_access_check, parse_passage_id_or_404


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

        cls.class1_2_active_student.teachers.add(cls.class1_1_teacher)
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
        with self.assertRaises(PermissionDenied):
            get_role_object_or_403(AnonymousUser())

    @patch("accounts.models.BaseUser.get_role_object")
    def test_get_role_object_or_403_with_none_cause_403(self, mock_role_object):
        mock_role_object.return_value = None
        with self.assertRaises(PermissionDenied):
            get_role_object_or_403(self.org1_admin)

    def test_get_role_object_or_403_returns_org_admin_object(self):
        role_object = get_role_object_or_403(self.org1_admin)
        self.assertIsInstance(role_object, OrganizationAdministrator)

    def test_get_role_object_or_403_returns_classroom_admin_object(self):
        role_object = get_role_object_or_403(self.class1_1_admin)
        self.assertIsInstance(role_object, ClassroomAdministrator)

    def test_get_role_object_or_403_returns_teacher_object(self):
        role_object = get_role_object_or_403(self.class1_1_teacher)
        self.assertIsInstance(role_object, Teacher)

    def test_get_role_object_or_403_returns_student_object(self):
        role_object = get_role_object_or_403(self.class1_1_active_student)
        self.assertIsInstance(role_object, Student)

    def test_get_role_object_or_403_returns_student_object_for_inactive_student(self):
        role_object = get_role_object_or_403(self.class1_1_inactive_student)
        self.assertIsInstance(role_object, Student)

    @patch("accounts.models.BaseUser.get_role_object")
    def test_get_role_object_or_403_when_get_role_object_raises_exception(self, mock_get_role_object):
        mock_get_role_object.side_effect = Exception("broken role relation")
        with self.assertRaises(PermissionDenied):
            get_role_object_or_403(self.org1_admin)

    def test_ensure_can_access_student_raise_403_for_anonymous_user(self):
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(AnonymousUser(), self.class1_1_active_student)

    def test_ensure_can_access_student_confirms_access_for_org_admin_with_right_student(self):
        result = ensure_can_access_student(self.org1_admin, self.class1_1_active_student)
        self.assertIsNone(result)

    def test_ensure_can_access_student_raise_403_when_student_argument_is_not_student_object(self):
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(self.org1_admin, self.class1_1_teacher)
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(self.org1_admin, self.class1_1_active_student.id)

    def test_ensure_can_access_student_raise_404_for_inactive_student(self):
        with self.assertRaises(Http404):
            ensure_can_access_student(self.org1_admin, self.class1_1_inactive_student)

    def test_ensure_can_access_student_raise_403_for_org_admin_with_other_org_student(self):
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(self.org1_admin, self.class2_active_student)

    def test_ensure_can_access_student_raise_404_for_org_admin_with_inactive_student_in_own_org(self):
        with self.assertRaises(Http404):
            ensure_can_access_student(self.org1_admin, self.class1_1_inactive_student)

    def test_ensure_can_access_student_confirms_access_for_classroom_admin_with_student_in_own_classroom(self):
        result = ensure_can_access_student(self.class1_1_admin, self.class1_1_active_student)
        self.assertIsNone(result)

    def test_ensure_can_access_student_raise_403_for_classroom_admin_with_student_in_other_classroom_same_org(self):
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(self.class1_1_admin, self.class1_2_active_student)

    def test_ensure_can_access_student_raise_404_for_classroom_admin_with_inactive_student_in_own_classroom(self):
        with self.assertRaises(Http404):
            ensure_can_access_student(self.class1_1_admin, self.class1_1_inactive_student)

    def test_ensure_can_access_student_raise_403_for_classroom_admin_with_other_org_student(self):
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(self.class1_1_admin, self.class2_active_student)

    def test_ensure_can_access_student_confirms_access_for_teacher_with_assigned_active_student(self):
        result = ensure_can_access_student(self.class1_1_teacher, self.class1_1_active_student)
        self.assertIsNone(result)

    def test_ensure_can_access_student_raise_403_for_teacher_with_unassigned_student_in_same_classroom(self):
        unassigned_student = Student.objects.create_user(
            username="class1_1_unassigned_student_lt",
            email="class1_1_unassigned_student_lt@example.com",
            password="pass123456",
            organization=self.org1,
            is_active=True,
            line_user_id="line_id_class1_1_unassigned_student_lt",
        )
        unassigned_student.classrooms.add(self.class1_1)

        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(self.class1_1_teacher, unassigned_student)

    def test_ensure_can_access_student_confirms_access_for_teacher_with_assigned_student_in_other_classroom_same_org(self):
        result = ensure_can_access_student(self.class1_1_teacher, self.class1_2_active_student)
        self.assertIsNone(result)

    def test_ensure_can_access_student_raise_403_for_teacher_with_student_in_other_org(self):
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(self.class1_1_teacher, self.class2_active_student)

    def test_ensure_can_access_student_raise_404_for_teacher_with_assigned_inactive_student(self):
        with self.assertRaises(Http404):
            ensure_can_access_student(self.class1_1_teacher, self.class1_1_inactive_student)

    def test_ensure_can_access_student_confirms_access_for_student_self(self):
        result = ensure_can_access_student(self.class1_1_active_student, self.class1_1_active_student)
        self.assertIsNone(result)

    def test_ensure_can_access_student_raise_404_for_inactive_student_user_self_access(self):
        with self.assertRaises(Http404):
            ensure_can_access_student(self.class1_1_inactive_student, self.class1_1_inactive_student)

    def test_ensure_can_access_student_raise_403_for_student_with_other_student_same_classroom(self):
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(self.class1_1_active_student, self.class1_2_active_student)

    def test_ensure_can_access_student_raise_403_for_student_with_other_student_other_org(self):
        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(self.class1_1_active_student, self.class2_active_student)

    @patch("listening_trainer.access_check.student_access_check.get_role_object_or_403")
    def test_ensure_can_access_student_raise_403_when_admin_role_object_has_no_can_manage_student(
        self,
        mock_get_role_object,
    ):
        class DummyRoleObject:
            pass

        mock_get_role_object.return_value = DummyRoleObject()

        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(self.org1_admin, self.class1_1_active_student)

    @patch("listening_trainer.access_check.student_access_check.get_role_object_or_403")
    def test_ensure_can_access_student_raise_403_when_student_role_object_is_not_student(
        self,
        mock_get_role_object,
    ):
        mock_get_role_object.return_value = self.org1_admin

        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(self.class1_1_active_student, self.class1_1_active_student)

    @patch("listening_trainer.access_check.student_access_check.get_role_object_or_403")
    def test_ensure_can_access_student_raise_403_for_unexpected_role(
        self,
        mock_get_role_object,
    ):
        class DummyRoleObject:
            pass

        mock_get_role_object.return_value = DummyRoleObject()

        user = OrganizationAdministrator.objects.create_user(
            username="unexpected_role_user_lt",
            email="unexpected_role_user_lt@example.com",
            password="pass123456",
        )
        user.role = "unexpected_role"

        with self.assertRaises(PermissionDenied):
            ensure_can_access_student(user, self.class1_1_active_student)

    def test_student_access_check_raise_403_when_student_id_missing(self):
        with self.assertRaises(PermissionDenied):
            student_access_check(self.org1_admin, None)

    def test_student_access_check_raise_403_when_student_id_is_empty_string(self):
        with self.assertRaises(PermissionDenied):
            student_access_check(self.org1_admin, "")

    def test_student_access_check_raise_404_when_student_id_does_not_exist(self):
        non_existent_id = uuid.uuid4()
        with self.assertRaises(Http404):
            student_access_check(self.org1_admin, non_existent_id)

    def test_student_access_check_with_invalid_uuid_string(self):
        with self.assertRaises(PermissionDenied):
            student_access_check(self.org1_admin, "not-a-uuid")

    def test_student_access_check_raise_404_when_student_is_inactive(self):
        with self.assertRaises(Http404):
            student_access_check(self.org1_admin, self.class1_1_inactive_student.id)

    def test_student_access_check_returns_student_when_access_allowed(self):
        student = student_access_check(self.org1_admin, self.class1_1_active_student.id)
        self.assertEqual(student, self.class1_1_active_student)

    def test_student_access_check_returns_student_for_org_admin_with_other_classroom_same_org_student(self):
        student = student_access_check(self.org1_admin, self.class1_2_active_student.id)
        self.assertEqual(student, self.class1_2_active_student)

    def test_student_access_check_raise_403_when_access_denied(self):
        with self.assertRaises(PermissionDenied):
            student_access_check(self.org1_admin, self.class2_active_student.id)

    def test_student_access_check_raise_403_for_classroom_admin_with_other_org_student(self):
        with self.assertRaises(PermissionDenied):
            student_access_check(self.class1_1_admin, self.class2_active_student.id)

    def test_ensure_can_access_student_confirms_access_for_classroom_admin_with_student_in_their_other_classroom(self):
        result = ensure_can_access_student(self.class1_2_admin, self.class1_2_active_student)
        self.assertIsNone(result)

    def test_student_access_check_passes_another_classroom_in_same_org_student(self):
        student = student_access_check(self.class1_1_teacher, self.class1_2_active_student.id)
        self.assertEqual(student, self.class1_2_active_student)

    def test_student_access_check_raise_403_when_org_is_not_the_same(self):
        with self.assertRaises(PermissionDenied):
            student_access_check(self.class1_1_teacher, self.class2_active_student.id)

    def test_student_access_check_raise_404_when_student_user_targets_inactive_student(self):
        with self.assertRaises(Http404):
            student_access_check(self.class1_1_active_student, self.class1_1_inactive_student.id)

    def test_not_id_but_student_raise_403(self):
        with self.assertRaises(PermissionDenied):
            student_access_check(self.org1_admin, self.class1_1_active_student)

    def test_org_admin_can_access_student_not_in_classroom_but_in_org(self):
        student_only_in_org = Student.objects.create_user(
            username="not classroom but org",
            line_user_id="not_classroom_but_org_line_user_id",
            organization=self.org1
        )
        student = student_access_check(self.org1_admin, student_only_in_org.id)
        self.assertEqual(student.id, student_only_in_org.id)
    
    def test_student_cannot_access_another_student_in_same_org(self):
        with self.assertRaises(PermissionDenied):
            student_access_check(self.class1_1_active_student, self.class1_2_active_student.id)

    def test_student_can_access_self(self):
        student = student_access_check(self.class1_1_active_student, self.class1_1_active_student.id)
        self.assertEqual(student.id, self.class1_1_active_student.id)

    def test_classroom_admin_can_access_students_in_classroom(self):
        student = student_access_check(self.class1_1_admin, self.class1_1_active_student.id)
        self.assertEqual(student.id, self.class1_1_active_student.id)

    def test_inactive_student_cannot_access_self(self):
        with self.assertRaises(Http404):
            student_access_check(self.class1_1_inactive_student, self.class1_1_inactive_student.id)

    def test_teacher_can_access_student_in_same_classroom(self):
        student = student_access_check(self.class1_1_teacher, self.class1_1_active_student.id)
        self.assertEqual(student.id, self.class1_1_active_student.id)


class ListeningPassageCheckTest(TestCase):
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

        cls.class1_2_active_student.teachers.add(cls.class1_1_teacher)
        cls.class2_active_student.teachers.add(cls.class1_1_teacher)

        cls.class1_1_active_student_textbook_passage = ListeningPassage.objects.create(
            title="sample passage title",
            content="this is sample passage content.",
            created_by=cls.class1_1_active_student,
            source_type="textbook",
        )

        cls.class1_1_active_student_eiken_passage = ListeningPassage.objects.create(
            title="sample passage title",
            content="this is sample passage content.",
            created_by=cls.class1_1_active_student,
            source_type="eiken",
        )

        cls.class1_2_active_student_eiken_passage = ListeningPassage.objects.create(
            title="sample passage title",
            content="this is sample passage content.",
            created_by=cls.class1_2_active_student,
            source_type="eiken",
        )

        cls.class2_active_student_textbook_passage = ListeningPassage.objects.create(
            title="sample passage title",
            content="this is sample passage content.",
            created_by=cls.class2_active_student,
            source_type="textbook",
        )

    def test_org_admin_can_access_passage_with_student_belonging_with_org(self):
        passage = passage_access_check(
            self.org1_admin,
            self.class1_1_active_student_textbook_passage.id,
            source_type="textbook",
            expected_student_id=self.class1_1_active_student.id
        )
        self.assertEqual(passage.id, self.class1_1_active_student_textbook_passage.id)

    def test_org_admin_cannot_access_passage_with_another_org_student(self):
        with self.assertRaises(Http404):
            passage_access_check(
                self.org1_admin,
                self.class2_active_student_textbook_passage.id,
            )

    def test_classroom_admin_can_access_passage_with_student_belonging_with_classroom(self):
        passage = passage_access_check(
            self.class1_1_admin,
            self.class1_1_active_student_eiken_passage.id,
            source_type="eiken",
            expected_student_id=self.class1_1_active_student.id
        )
        self.assertEqual(passage.id, self.class1_1_active_student_eiken_passage.id)

    def test_classroom_admin_cannot_access_passage_with_another_org_student(self):
        with self.assertRaises(Http404):
            passage_access_check(
                self.class1_1_admin,
                self.class2_active_student_textbook_passage.id,
            )

    def test_classroom_admin_cannot_access_passage_with_another_classroom_student(self):
        with self.assertRaises(Http404):
            passage_access_check(
                self.class1_1_admin,
                self.class1_2_active_student_eiken_passage.id,
            )

    def test_teacher_can_access_passage_with_assigned_student(self):
        passage = passage_access_check(
            self.class1_1_teacher,
            self.class1_1_active_student_textbook_passage.id,
        )
        self.assertEqual(passage.id, self.class1_1_active_student_textbook_passage.id)

    def test_teacher_can_access_passage_with_assigned_student_in_another_classroom(self):
        passage = passage_access_check(
            self.class1_1_teacher,
            self.class1_2_active_student_eiken_passage.id,
        )
        self.assertEqual(passage.id, self.class1_2_active_student_eiken_passage.id)

    def test_teacher_cannot_access_passage_with_assigned_student_in_another_org(self):
        with self.assertRaises(Http404):
            passage_access_check(
                self.class1_1_teacher,
                self.class2_active_student_textbook_passage.id
            )

    def test_student_can_access_their_passage(self):
        passage = passage_access_check(
            self.class1_1_active_student,
            self.class1_1_active_student_eiken_passage.id,
        )
        self.assertEqual(passage.id, self.class1_1_active_student_eiken_passage.id)

    def test_student_cannot_access_any_other_passage(self):
        passage_ids = [
            self.class1_2_active_student_eiken_passage.id,
            self.class2_active_student_textbook_passage.id,
        ]
        for passage_id in passage_ids:
            with self.assertRaises(Http404):
                passage_access_check(self.class1_1_active_student, passage_id)

    def test_all_users_cannot_access_passage_when_source_type_is_wrong(self):
        users = [
            self.org1_admin,
            self.class1_1_admin,
            self.class1_1_teacher,
            self.class1_1_active_student
        ]
        for user in users:
            with self.assertRaises(Http404):
                passage_access_check(
                    user,
                    self.class1_1_active_student_eiken_passage.id,
                    source_type="textbook"
                )

    def test_all_users_cannot_access_passage_when_expected_student_id_is_wrong(self):
        users = [
            self.org1_admin,
            self.class1_1_admin,
            self.class1_1_teacher,
            self.class1_1_active_student
        ]
        for user in users:
            with self.assertRaises(Http404):
                passage_access_check(
                    user,
                    self.class1_1_active_student_eiken_passage.id,
                    expected_student_id=self.class1_2_active_student.id
                )

    def test_all_users_cannot_access_without_passage_id(self):
        users = [
            self.org1_admin,
            self.class1_1_admin,
            self.class1_1_teacher,
            self.class1_1_active_student
        ]
        for user in users:
            with self.assertRaises(Http404):
                passage_access_check(user, "")

    def test_all_users_cannot_access_without_not_int_passage_id(self):
        users = [
            self.org1_admin,
            self.class1_1_admin,
            self.class1_1_teacher,
            self.class1_1_active_student
        ]
        for user in users:
            with self.assertRaises(Http404):
                passage_access_check(user, "abc")

    def test_all_user_cannot_access_when_passage_id_is_passage_self(self):
        users = [
            self.org1_admin,
            self.class1_1_admin,
            self.class1_1_teacher,
            self.class1_1_active_student
        ]
        for user in users:
            with self.assertRaises(Http404):
                passage_access_check(
                    user,
                    self.class1_1_active_student_eiken_passage,
                    source_type="eiken",
                    expected_student_id=self.class1_1_active_student.id
                )

    def test_all_user_cannot_access_when_source_type_does_not_exist(self):
        users = [
            self.org1_admin,
            self.class1_1_admin,
            self.class1_1_teacher,
            self.class1_1_active_student
        ]
        for user in users:
            with self.assertRaises(Http404):
                passage_access_check(
                    user,
                    self.class1_1_active_student_textbook_passage.id,
                    source_type="unexpected type")

    def test_all_user_cannot_access_when_creator_does_not_exist(self):
        passage_without_student = ListeningPassage.objects.create(
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
                passage_access_check(user, passage_without_student.id, source_type="eiken")

    def test_all_user_cannot_access_passage_with_inactive_student(self):
        passage_with_inactive_student = ListeningPassage.objects.create(
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
                passage_access_check(user, passage_with_inactive_student.id, source_type="eiken")

    def test_passage_access_check_passes_when_expected_student_id_is_same_uuid_string(self):
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
        unassigned_student = Student.objects.create_user(
            username="unassigned_student_lt",
            email="unassigned_student_lt@example.com",
            password="pass123456",
            organization=self.org1,
            is_active=True,
            line_user_id="line_unassigned_student_lt",
        )
        unassigned_student.classrooms.add(self.class1_1)

        passage = ListeningPassage.objects.create(
            title="unassigned",
            content="content",
            created_by=unassigned_student,
            source_type="textbook",
        )

        with self.assertRaises(Http404):
            passage_access_check(self.class1_1_teacher, passage.id)

    def test_student_cannot_access_same_classroom_other_student_passage(self):
        other_passage = ListeningPassage.objects.create(
            title="other",
            content="content",
            created_by=self.class1_2_active_student,
            source_type="eiken",
        )

        with self.assertRaises(Http404):
            passage_access_check(self.class1_1_active_student, other_passage.id)

    def test_passage_access_check_does_not_accept_zero(self):
        with self.assertRaises(Http404):
            passage_access_check(self.org1_admin, 0)

    def test_passage_access_check_does_not_accept_negative_value(self):
        with self.assertRaises(Http404):
            passage_access_check(self.org1_admin, -1)

    def test_passage_access_check_does_not_accept_decimal(self):
        with self.assertRaises(Http404):
            passage_access_check(self.org1_admin, "1.5")

    def test_anonymous_user_cannot_access_passage(self):
        with self.assertRaises(Http404):
            passage_access_check(
                AnonymousUser(),
                self.class1_1_active_student_textbook_passage.id,
            )

    def test_visible_to_for_teacher_excludes_other_org_even_if_assigned(self):
        qs = ListeningPassage.objects.visible_to(self.class1_1_teacher)
        self.assertNotIn(self.class2_active_student_textbook_passage, qs)

    def test_parse_passage_id_or_404_raises_404_for_zero(self):
        with self.assertRaises(Http404):
            parse_passage_id_or_404(self.org1_admin, 0)

    def test_parse_passage_id_or_404_raises_404_for_negative_integer(self):
        with self.assertRaises(Http404):
            parse_passage_id_or_404(self.org1_admin, -1)

    def test_parse_passage_id_or_404_raises_404_for_float_like_string(self):
        with self.assertRaises(Http404):
            parse_passage_id_or_404(self.org1_admin, "1.5")

    def test_non_existent_passage_id_raise_404(self):
        with self.assertRaises(Http404):
            passage_access_check(self.org1_admin, 99999)

    def test_none_passage_id_raise_404(self):
        with self.assertRaises(Http404):
            passage_access_check(self.org1_admin, None)

    def test_passage_instead_of_passage_id_raise_404(self):
        with self.assertRaises(Http404):
            passage_access_check(self.org1_admin, self.class1_1_active_student_eiken_passage)
