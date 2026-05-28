from django.test import TestCase
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import AnonymousUser


from accounts.models import BaseUser, Organization, OrganizationAdministrator
from accounts.selectors import visible_organization_administrators_qs


class VisibleOrganizationAdministratorsQsTests(TestCase):


    def setUp(self):
        self.org = Organization.objects.create(name="org")

        self.user = OrganizationAdministrator.objects.create_user(
            email="admin@example.com",
            password="test",
            role="organization_administrator",
            username="Admin",
        )
        self.user.organizations.add(self.org)

        self.other_admin = OrganizationAdministrator.objects.create_user(
            email="other@example.com",
            password="test",
            role="organization_administrator",
            username="Other",
        )

    def _add_perm(self, user, codename, model):
        content_type = ContentType.objects.get_for_model(model)
        perm = Permission.objects.get(content_type=content_type, codename=codename)
        user.user_permissions.add(perm)

    def test_unauthenticated_user_gets_none(self):
        user = AnonymousUser()
        qs = visible_organization_administrators_qs(user)
        self.assertEqual(qs.count(), 0)

    def test_user_without_permission_gets_none(self):
        qs = visible_organization_administrators_qs(self.user)
        self.assertEqual(qs.count(), 0)

    def test_view_all_returns_all(self):
        self._add_perm(self.user, "view_organizationadministrator", OrganizationAdministrator)
        self._add_perm(self.user, "view_all_organization_administrators", OrganizationAdministrator)

        qs = visible_organization_administrators_qs(self.user)

        self.assertEqual(qs.count(), 2)

    def test_org_admin_returns_only_same_org(self):
        self._add_perm(self.user, "view_organizationadministrator", OrganizationAdministrator)
        qs = visible_organization_administrators_qs(self.user)
        self.assertEqual(list(qs), [self.user])

    def test_non_org_admin_gets_none(self):
        user = BaseUser.objects.create_user(
            email="teacher@example.com",
            password="test",
            role="teacher",
        )

        self._add_perm(user, "view_organizationadministrator", OrganizationAdministrator)

        qs = visible_organization_administrators_qs(user)

        self.assertEqual(qs.count(), 0)
