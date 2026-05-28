from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import BaseUser, Organization
from accounts.views.auth_views import CustomLoginView


class AuthViewsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _make_user(self, *, role: str, is_superuser: bool = False):
        return BaseUser.objects.create_user(
            email=f"{role}@example.com",
            password="testpass123",
            username=f"{role}_user",
            role=role,
            is_superuser=is_superuser,
        )

    def _build_login_view(self, user):
        request = self.factory.get(reverse("accounts_auth:login"))
        request.user = user
        view = CustomLoginView()
        view.setup(request)
        return view

    def test_get_success_url_for_superuser(self):
        user = self._make_user(role="organization_administrator", is_superuser=True)

        view = self._build_login_view(user)

        self.assertEqual(view.get_success_url(), reverse("admin:index"))

    def test_get_success_url_for_organization_administrator(self):
        user = self._make_user(role="organization_administrator")

        view = self._build_login_view(user)

        self.assertEqual(
            view.get_success_url(),
            reverse("organization_admin:classroom_list"),
        )

    def test_get_success_url_for_classroom_administrator(self):
        user = self._make_user(role="classroom_administrator")

        view = self._build_login_view(user)

        self.assertEqual(
            view.get_success_url(),
            reverse("organization_admin:classroom_list"),
        )

    def test_get_success_url_for_teacher(self):
        user = self._make_user(role="teacher")

        view = self._build_login_view(user)

        self.assertEqual(
            view.get_success_url(),
            reverse("organization_admin:teacher_dashboard"),
        )

    def test_get_success_url_for_student(self):
        user = self._make_user(role="student")

        view = self._build_login_view(user)

        self.assertEqual(
            view.get_success_url(),
            reverse("student:home"),
        )

    def test_get_success_url_raises_permission_denied_for_unknown_role(self):
        user = self._make_user(role="unknown_role")

        view = self._build_login_view(user)

        with self.assertRaises(PermissionDenied):
            view.get_success_url()

    def test_logout_get_returns_405(self):
        user = self._make_user(role="organization_administrator")
        self.client.force_login(user)

        resp = self.client.get(reverse("accounts_auth:logout"))

        self.assertEqual(resp.status_code, 405)

    def test_logout_post_logs_out_and_redirects_to_login(self):
        user = self._make_user(role="organization_administrator")
        self.client.force_login(user)

        resp = self.client.post(reverse("accounts_auth:logout"))

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("accounts_auth:login"))

        resp_after = self.client.get(reverse("accounts_auth:login"))
        self.assertTrue(resp_after.wsgi_request.user.is_anonymous)

    def test_login_redirects_to_next_when_present(self):
        user = self._make_user(role="organization_administrator")
        student = self._make_user(role="student")
        org = Organization.objects.create(name="org1")
        student.organization = org
        student.save()

        target_url = reverse(
            "organization_admin:assign_classroom",
            kwargs={"pk": student.pk},
        )

        resp = self.client.post(
            reverse("accounts_auth:login") + f"?next={target_url}",
            data={
                "username": user.email,
                "password": "testpass123",
            },
        )

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], target_url)


class CustomLoginViewDispatchTests(TestCase):
    def _make_student(self):
        return BaseUser.objects.create_user(
            email="student@example.com",
            password="testpass123",
            username="student_user",
            role="student",
        )

    def test_authenticated_user_with_next_is_redirected_to_next(self):
        user = self._make_student()
        self.client.force_login(user)
        next_url = reverse("student:home")

        resp = self.client.get(
            reverse("accounts_auth:login") + f"?next={next_url}"
        )

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], next_url)

    def test_authenticated_user_without_next_is_redirected_to_role_home(self):
        user = self._make_student()
        self.client.force_login(user)

        resp = self.client.get(reverse("accounts_auth:login"))

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("student:home"))

    def test_unauthenticated_user_sees_login_form(self):
        resp = self.client.get(reverse("accounts_auth:login"))

        self.assertEqual(resp.status_code, 200)

    def test_external_next_url_is_not_redirected_to(self):
        user = self._make_student()
        self.client.force_login(user)

        resp = self.client.get(
            reverse("accounts_auth:login") + "?next=https://evil.example.com"
        )

        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("evil.example.com", resp["Location"])
