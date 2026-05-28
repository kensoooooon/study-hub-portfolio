from django.test import TestCase
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import AnonymousUser


from accounts.models import BaseUser, Organization, OrganizationAdministrator
from accounts.selectors import visible_organizations_qs


class VisibleOrganizationsQsTests(TestCase):

    def setUp(self):
        self.org1 = Organization.objects.create(name="org1")
        self.org2 = Organization.objects.create(name="org2")

        self.user = OrganizationAdministrator.objects.create_user(
            email="admin@example.com",
            password="test",
            role="organization_administrator",
            username="Admin",
        )
        self.user.organizations.add(self.org1)

    def _add_perm(self, user, codename, model):
        content_type = ContentType.objects.get_for_model(model)
        perm = Permission.objects.get(content_type=content_type, codename=codename)
        user.user_permissions.add(perm)

    def test_unauthenticated_user_gets_none(self):
        user = AnonymousUser()
        qs = visible_organizations_qs(user)
        self.assertEqual(qs.count(), 0)

    def test_user_without_permission_gets_none(self):
        qs = visible_organizations_qs(self.user)
        self.assertEqual(qs.count(), 0)

    def test_view_all_permission_returns_all(self):
        self._add_perm(self.user, "view_organization", Organization)
        self._add_perm(self.user, "view_all_organizations", Organization)

        qs = visible_organizations_qs(self.user)

        self.assertEqual(qs.count(), 2)

    def test_org_admin_returns_only_accessible(self):
        self._add_perm(self.user, "view_organization", Organization)

        qs = visible_organizations_qs(self.user)

        self.assertEqual(list(qs), [self.org1])

    def test_non_org_admin_gets_none(self):
        user = BaseUser.objects.create_user(
            email="teacher@example.com",
            password="test",
            role="teacher",
        )

        self._add_perm(user, "view_organization", Organization)

        qs = visible_organizations_qs(user)

        self.assertEqual(qs.count(), 0)
