from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import Organization, OrganizationAdministrator


def _create_user(
    *,
    email: str,
    role: str = "teacher",
    username: str = "U",
    password: str = "testpass123",
    is_first_login: bool = False,
):
    User = get_user_model()
    return User.objects.create_user(
        email=email,
        password=password,
        role=role,
        username=username,
        is_first_login=is_first_login,
    )


def _grant_org_perm(user, codename: str) -> None:
    ct = ContentType.objects.get_for_model(Organization)
    perm = Permission.objects.get(content_type=ct, codename=codename)
    user.user_permissions.add(perm)


def _grant_org_view_perms(user) -> None:
    _grant_org_perm(user, "view_organization")
    _grant_org_perm(user, "view_all_organizations")


def _grant_ops_group(user) -> None:
    call_command("setup_ops_organizations")
    group = Group.objects.get(name="ops_organizations")
    user.groups.add(group)


class OpsOrganizationAnonymousAccessTests(TestCase):
    def test_list_returns_404_for_anonymous(self):
        resp = self.client.get(reverse("ops_organization:list"))
        self.assertEqual(resp.status_code, 404)

    def test_detail_returns_404_for_anonymous(self):
        org = Organization.objects.create(name="Anonymous Org")

        resp = self.client.get(
            reverse("ops_organization:detail", kwargs={"pk": org.pk})
        )

        self.assertEqual(resp.status_code, 404)

    def test_create_returns_404_for_anonymous(self):
        resp = self.client.get(reverse("ops_organization:create"))
        self.assertEqual(resp.status_code, 404)

    def test_create_admin_invitation_returns_404_for_anonymous(self):
        org = Organization.objects.create(name="Anonymous Invite Org")

        resp = self.client.get(
            reverse(
                "ops_organization:create_admin_invitation",
                kwargs={"organization_id": org.pk},
            )
        )

        self.assertEqual(resp.status_code, 404)


class OpsOrganizationListDetailUITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="Org A")
        cls.org2 = Organization.objects.create(name="Org B")

    def test_list_returns_404_when_missing_view_perm(self):
        user = _create_user(email="no_view@example.com", username="NoView")
        self.client.force_login(user)

        url = reverse("ops_organization:list")
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 404)

    def test_list_ok_and_shows_orgs_when_has_view_perm(self):
        user = _create_user(email="can_view@example.com", username="CanView")
        _grant_org_view_perms(user)
        self.client.force_login(user)

        url = reverse("ops_organization:list")
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Org A")
        self.assertContains(resp, "Org B")

    def test_detail_returns_404_when_missing_view_perm(self):
        user = _create_user(email="no_view2@example.com", username="NoView2")
        self.client.force_login(user)

        url = reverse("ops_organization:detail", kwargs={"pk": self.org1.pk})
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 404)

    def test_detail_ok_when_has_view_perm(self):
        user = _create_user(email="can_view2@example.com", username="CanView2")
        _grant_org_view_perms(user)
        self.client.force_login(user)

        url = reverse("ops_organization:detail", kwargs={"pk": self.org1.pk})
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Org A")


class OpsOrganizationCreateUITests(TestCase):
    def test_get_create_returns_404_without_add_perm(self):
        user = _create_user(email="no_add@example.com", username="NoAdd")
        self.client.force_login(user)

        url = reverse("ops_organization:create")
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 404)

    def test_post_create_creates_org_and_redirects_to_detail(self):
        user = _create_user(email="can_add@example.com", username="CanAdd")
        _grant_org_perm(user, "add_organization")
        _grant_org_view_perms(user)
        self.client.force_login(user)

        url = reverse("ops_organization:create")
        resp = self.client.post(url, data={"name": "Org New"})

        self.assertEqual(resp.status_code, 302)

        created = Organization.objects.get(name="Org New")
        expected = reverse("ops_organization:detail", kwargs={"pk": created.pk})
        self.assertEqual(resp["Location"], expected)

    def test_post_create_duplicate_name_shows_form_error(self):
        Organization.objects.create(name="Org Dup")

        user = _create_user(email="can_add2@example.com", username="CanAdd2")
        _grant_org_perm(user, "add_organization")
        _grant_org_view_perms(user)
        self.client.force_login(user)

        url = reverse("ops_organization:create")
        resp = self.client.post(url, data={"name": "Org Dup"})

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "この組織名は既に登録されています")


class OpsOrganizationScopedOrgAdminUITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="Scoped Org 1")
        cls.org2 = Organization.objects.create(name="Scoped Org 2")

        cls.org_admin = OrganizationAdministrator.objects.create_user(
            email="scoped-admin@example.com",
            password="testpass123",
            username="ScopedAdmin",
        )
        cls.org_admin.organizations.add(cls.org1)
        _grant_org_perm(cls.org_admin, "view_organization")

    def test_list_shows_only_accessible_organization(self):
        self.client.force_login(self.org_admin)

        resp = self.client.get(reverse("ops_organization:list"))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Scoped Org 1")
        self.assertNotContains(resp, "Scoped Org 2")

    def test_detail_allows_access_to_owned_org(self):
        self.client.force_login(self.org_admin)

        resp = self.client.get(
            reverse("ops_organization:detail", kwargs={"pk": self.org1.pk})
        )

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Scoped Org 1")

    def test_detail_returns_404_for_other_org(self):
        self.client.force_login(self.org_admin)

        resp = self.client.get(
            reverse("ops_organization:detail", kwargs={"pk": self.org2.pk})
        )

        self.assertEqual(resp.status_code, 404)


class OpsOrganizationGroupPermissionUITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="Group Org 1")
        cls.org2 = Organization.objects.create(name="Group Org 2")

        cls.org_admin = OrganizationAdministrator.objects.create_user(
            email="group-admin@example.com",
            password="testpass123",
            username="GroupAdmin",
        )
        cls.org_admin.organizations.add(cls.org1)

        _grant_ops_group(cls.org_admin)

    def test_list_allows_access_via_group_permission(self):
        self.client.force_login(self.org_admin)

        resp = self.client.get(reverse("ops_organization:list"))

        self.assertEqual(resp.status_code, 200)

    def test_list_shows_all_organizations_via_ops_group(self):
        self.client.force_login(self.org_admin)

        resp = self.client.get(reverse("ops_organization:list"))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Group Org 1")
        self.assertContains(resp, "Group Org 2")

    def test_detail_allows_access_to_other_org_via_ops_group(self):
        self.client.force_login(self.org_admin)

        resp = self.client.get(
            reverse("ops_organization:detail", kwargs={"pk": self.org2.pk})
        )

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Group Org 2")

    def test_create_allows_access_via_group_permission(self):
        self.client.force_login(self.org_admin)

        resp = self.client.get(reverse("ops_organization:create"))

        self.assertEqual(resp.status_code, 200)


class OpsOrganizationInvitationGroupPermissionUITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="Invite Org 1")
        cls.org2 = Organization.objects.create(name="Invite Org 2")

        cls.org_admin = OrganizationAdministrator.objects.create_user(
            email="invite-group-admin@example.com",
            password="testpass123",
            username="InviteGroupAdmin",
        )
        cls.org_admin.organizations.add(cls.org1)

        _grant_ops_group(cls.org_admin)

    def test_create_admin_invitation_get_allows_access_via_ops_group(self):
        self.client.force_login(self.org_admin)

        resp = self.client.get(
            reverse(
                "ops_organization:create_admin_invitation",
                kwargs={"organization_id": self.org1.pk},
            )
        )

        self.assertEqual(resp.status_code, 200)

    def test_create_admin_invitation_get_allows_other_org_via_ops_group(self):
        self.client.force_login(self.org_admin)

        resp = self.client.get(
            reverse(
                "ops_organization:create_admin_invitation",
                kwargs={"organization_id": self.org2.pk},
            )
        )

        self.assertEqual(resp.status_code, 200)


class OpsOrganizationInvitationScopedAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="Scoped Invite Org 1")
        cls.org2 = Organization.objects.create(name="Scoped Invite Org 2")

        cls.org_admin = OrganizationAdministrator.objects.create_user(
            email="scoped-invite-admin@example.com",
            password="testpass123",
            username="ScopedInviteAdmin",
        )
        cls.org_admin.organizations.add(cls.org1)
        _grant_org_perm(cls.org_admin, "view_organization")
        _grant_org_perm(cls.org_admin, "invite_organization_administrator")

    def test_create_admin_invitation_get_returns_404_for_other_org(self):
        self.client.force_login(self.org_admin)

        resp = self.client.get(
            reverse(
                "ops_organization:create_admin_invitation",
                kwargs={"organization_id": self.org2.pk},
            )
        )

        self.assertEqual(resp.status_code, 404)

    @patch("accounts.views.ops_organization_views.invite_organization_administrator")
    def test_create_admin_invitation_post_returns_404_for_other_org(
        self,
        mock_invite,
    ):
        self.client.force_login(self.org_admin)

        resp = self.client.post(
            reverse(
                "ops_organization:create_admin_invitation",
                kwargs={"organization_id": self.org2.pk},
            ),
            data={"email": "new-admin@example.com"},
        )

        self.assertEqual(resp.status_code, 404)
        mock_invite.assert_not_called()
