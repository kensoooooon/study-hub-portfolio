from __future__ import annotations

from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts.context_processors import (
    debug_mode,
    homepage_url,
    unassigned_students_count,
)
from accounts.models import (
    BaseUser,
    Organization,
    OrganizationAdministrator,
    Student,
    Classroom,
)


class ContextProcessorsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request_with_user(self, user):
        request = self.factory.get("/")
        request.user = user
        return request

    def _make_base_user(self, *, role: str, is_first_login: bool = False):
        return BaseUser.objects.create_user(
            email=f"{role}@example.com",
            password="testpass123",
            username=f"{role}_user",
            role=role,
            is_first_login=is_first_login,
        )

    def test_homepage_url_for_anonymous_user(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()

        result = homepage_url(request)

        self.assertEqual(
            result["homepage_url"],
            reverse("accounts_auth:login"),
        )

    def test_homepage_url_for_organization_administrator(self):
        user = self._make_base_user(role="organization_administrator")
        request = self._request_with_user(user)

        result = homepage_url(request)

        self.assertEqual(
            result["homepage_url"],
            reverse("organization_admin:classroom_list"),
        )

    def test_homepage_url_for_classroom_administrator(self):
        user = self._make_base_user(role="classroom_administrator")
        request = self._request_with_user(user)

        result = homepage_url(request)

        self.assertEqual(
            result["homepage_url"],
            reverse("organization_admin:classroom_list"),
        )

    def test_homepage_url_for_teacher(self):
        user = self._make_base_user(role="teacher")
        request = self._request_with_user(user)

        result = homepage_url(request)

        self.assertEqual(
            result["homepage_url"],
            reverse("organization_admin:teacher_dashboard"),
        )

    def test_homepage_url_for_student(self):
        user = self._make_base_user(role="student")
        request = self._request_with_user(user)

        result = homepage_url(request)

        self.assertEqual(
            result["homepage_url"],
            reverse("student:home"),
        )

    def test_homepage_url_for_unknown_role_falls_back_to_login(self):
        user = self._make_base_user(role="unknown_role")
        request = self._request_with_user(user)

        result = homepage_url(request)

        self.assertEqual(
            result["homepage_url"],
            reverse("accounts_auth:login"),
        )

    def test_unassigned_students_count_returns_zero_for_anonymous_user(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()

        result = unassigned_students_count(request)

        self.assertEqual(result["unassigned_student_count"], 0)

    def test_unassigned_students_count_returns_zero_for_non_org_admin(self):
        user = self._make_base_user(role="teacher")
        request = self._request_with_user(user)

        result = unassigned_students_count(request)

        self.assertEqual(result["unassigned_student_count"], 0)

    def test_unassigned_students_count_returns_zero_when_role_object_is_none(self):
        user = self._make_base_user(role="organization_administrator")
        user.get_role_object = Mock(return_value=None)
        request = self._request_with_user(user)

        result = unassigned_students_count(request)

        self.assertEqual(result["unassigned_student_count"], 0)

    def test_unassigned_students_count_for_org_admin_counts_only_matching_students(self):
        org1 = Organization.objects.create(name="Org1")
        org2 = Organization.objects.create(name="Org2")

        org_admin = OrganizationAdministrator.objects.create_user(
            email="orgadmin@example.com",
            password="testpass123",
            username="orgadmin",
        )
        org_admin.organizations.add(org1)

        request = self._request_with_user(org_admin)

        # カウント対象:
        # - classrooms が未割り当て
        # - line_user_id がある
        # - organization が org1
        Student.objects.create_user(
            email="s1@example.com",
            password="testpass123",
            username="student1",
            organization=org1,
            line_user_id="line-001",
        )

        # 対象外: line_user_id がない
        Student.objects.create_user(
            email="s2@example.com",
            password="testpass123",
            username="student2",
            organization=org1,
            line_user_id=None,
        )

        # 対象外: 別組織
        Student.objects.create_user(
            email="s3@example.com",
            password="testpass123",
            username="student3",
            organization=org2,
            line_user_id="line-003",
        )

        result = unassigned_students_count(request)

        self.assertEqual(result["unassigned_student_count"], 1)

    @override_settings(DEBUG=True)
    def test_debug_mode_returns_true_when_debug_true(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()

        result = debug_mode(request)

        self.assertTrue(result["is_debug"])

    @override_settings(DEBUG=False)
    def test_debug_mode_returns_false_when_debug_false(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()

        result = debug_mode(request)

        self.assertFalse(result["is_debug"])

    def test_unassigned_students_count_excludes_students_with_classroom(self):
        org1 = Organization.objects.create(name="Org1")
        org_admin = OrganizationAdministrator.objects.create_user(
            email="orgadmin2@example.com",
            password="testpass123",
            username="orgadmin2",
        )
        org_admin.organizations.add(org1)

        request = self._request_with_user(org_admin)

        unassigned = Student.objects.create_user(
            email="s10@example.com",
            password="testpass123",
            username="student10",
            organization=org1,
            line_user_id="line-010",
        )

        assigned = Student.objects.create_user(
            email="s11@example.com",
            password="testpass123",
            username="student11",
            organization=org1,
            line_user_id="line-011",
        )

        classroom = Classroom.objects.create(
            name="Class A",
            organization=org1,
        )
        assigned.classrooms.add(classroom)

        result = unassigned_students_count(request)

        self.assertEqual(result["unassigned_student_count"], 1)
