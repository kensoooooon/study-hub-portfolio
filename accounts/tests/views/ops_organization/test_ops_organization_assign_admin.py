from __future__ import annotations

from uuid import uuid4

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from accounts.models import Organization, OrganizationAdministrator


def _grant_perm(user, model, codename: str) -> None:
    ct = ContentType.objects.get_for_model(model)
    perm = Permission.objects.get(content_type=ct, codename=codename)
    user.user_permissions.add(perm)


def _grant_assign_flow_perms(user) -> None:
    # 組織を見る
    _grant_perm(user, Organization, "view_organization")
    _grant_perm(user, Organization, "view_all_organizations")

    # 組織管理者候補を見る
    _grant_perm(user, OrganizationAdministrator, "view_organizationadministrator")
    _grant_perm(user, OrganizationAdministrator, "view_all_organization_administrators")

    # 割当操作
    _grant_perm(user, Organization, "assign_organization_administrator")


class OpsOrganizationAssignAdminFlowTests(TestCase):
    """
    組織管理者割当 (select -> confirm -> execute) のテスト
    """

    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="Org 1")
        cls.org2 = Organization.objects.create(name="Org 2")

        cls.operator = OrganizationAdministrator.objects.create_user(
            email="operator@example.com",
            password="pass12345",
            username="Operator",
            role="organization_administrator",
        )
        _grant_assign_flow_perms(cls.operator)

        cls.cand_ok = OrganizationAdministrator.objects.create_user(
            email="cand_ok@example.com",
            password="pass12345",
            username="Cand OK",
            role="organization_administrator",
        )

        cls.cand_already = OrganizationAdministrator.objects.create_user(
            email="cand_already@example.com",
            password="pass12345",
            username="Cand Already",
            role="organization_administrator",
        )
        cls.cand_already.organizations.add(cls.org1)

        cls.no_perm_operator = OrganizationAdministrator.objects.create_user(
            email="no_perm@example.com",
            password="pass12345",
            username="No Perm",
            role="organization_administrator",
        )

    def login_operator(self):
        ok = self.client.login(email="operator@example.com", password="pass12345")
        self.assertTrue(ok)

    def login_no_perm(self):
        ok = self.client.login(email="no_perm@example.com", password="pass12345")
        self.assertTrue(ok)

    def test_select_view_requires_assign_permission_masked_404(self):
        self.login_no_perm()
        url = reverse("ops_organization:assign_admin", kwargs={"pk": self.org1.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_select_view_shows_candidates_excluding_already_assigned(self):
        self.login_operator()
        url = reverse("ops_organization:assign_admin", kwargs={"pk": self.org1.pk})
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Cand OK")
        self.assertNotContains(resp, "Cand Already")

        self.assertIn("has_candidates", resp.context)
        self.assertTrue(resp.context["has_candidates"])

    def test_select_post_valid_renders_confirm(self):
        self.login_operator()
        url = reverse("ops_organization:assign_admin", kwargs={"pk": self.org1.pk})
        resp = self.client.post(url, data={"admins": [str(self.cand_ok.pk)]})

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Cand OK")
        self.assertContains(resp, 'name="admin_ids"')
        self.assertContains(resp, str(self.cand_ok.pk))

    def test_confirm_post_assigns_admin_and_redirects(self):
        self.login_operator()
        url = reverse("ops_organization:assign_admin_confirm", kwargs={"pk": self.org1.pk})
        resp = self.client.post(url, data={"admin_ids": [str(self.cand_ok.pk)]})

        self.assertEqual(resp.status_code, 302)

        self.org1.refresh_from_db()
        self.assertTrue(self.org1.administrators.filter(pk=self.cand_ok.pk).exists())

    def test_confirm_post_rejects_candidate_outside_queryset(self):
        self.login_operator()
        url = reverse("ops_organization:assign_admin_confirm", kwargs={"pk": self.org1.pk})
        resp = self.client.post(url, data={"admin_ids": [str(self.cand_already.pk)]})

        self.assertEqual(resp.status_code, 404)

    def test_confirm_post_rejects_nonexistent_id(self):
        self.login_operator()
        url = reverse("ops_organization:assign_admin_confirm", kwargs={"pk": self.org1.pk})
        bogus = str(uuid4())
        resp = self.client.post(url, data={"admin_ids": [bogus]})

        self.assertEqual(resp.status_code, 404)

    def test_confirm_post_with_no_admin_ids_redirects_to_list(self):
        self.login_operator()
        url = reverse("ops_organization:assign_admin_confirm", kwargs={"pk": self.org1.pk})
        resp = self.client.post(url, data={})

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("ops_organization:list"))

    def test_confirm_post_multiple_ids_assigns_all(self):
        self.login_operator()

        cand2 = OrganizationAdministrator.objects.create_user(
            email="cand2@example.com",
            password="pass12345",
            username="Cand 2",
            role="organization_administrator",
        )

        url = reverse("ops_organization:assign_admin_confirm", kwargs={"pk": self.org2.pk})
        resp = self.client.post(
            url,
            data={"admin_ids": [str(self.cand_ok.pk), str(cand2.pk)]},
        )

        self.assertEqual(resp.status_code, 302)

        self.org2.refresh_from_db()
        self.assertTrue(self.org2.administrators.filter(pk=self.cand_ok.pk).exists())
        self.assertTrue(self.org2.administrators.filter(pk=cand2.pk).exists())
