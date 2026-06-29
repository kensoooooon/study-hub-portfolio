from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.contrib.messages import get_messages
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Organization, OrganizationAdministrator
from accounts.services.exceptions import (
    AnotherRoleExistsInAnotherOrganizationError,
    ExistingUserWrongRoleError,
    InvitationAlreadyExistsError,
    InvitationOrganizationNotFoundError,
    OrganizationAdministratorAlreadyAssignedError,
    OrganizationAdministratorExistsInAnotherOrganizationError,
)


def _grant_org_perm(user, codename: str) -> None:
    ct = ContentType.objects.get_for_model(Organization)
    perm = Permission.objects.get(content_type=ct, codename=codename)
    user.user_permissions.add(perm)


def _grant_invite_flow_perms(user) -> None:
    # dispatch() で visible_organizations_qs → require_can_invite_organization_administrator
    # の順に通るので両方必要
    _grant_org_perm(user, "view_organization")
    _grant_org_perm(user, "view_all_organizations")
    _grant_org_perm(user, "invite_organization_administrator")


@override_settings(APP_PUBLIC_BASE_URL="https://example.com")
class OpsOrganizationInvitationCreateUITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org1 = Organization.objects.create(name="Org A")
        cls.org2 = Organization.objects.create(name="Org B")

        cls.operator = OrganizationAdministrator.objects.create_user(
            email="operator@example.com",
            password="testpass123",
            username="Operator",
            is_first_login=False,
        )
        _grant_invite_flow_perms(cls.operator)
        cls.operator.organizations.add(cls.org1)

        cls.no_perm_user = OrganizationAdministrator.objects.create_user(
            email="no_perm@example.com",
            password="testpass123",
            username="NoPerm",
            is_first_login=False,
        )

    def login_operator(self):
        self.client.force_login(self.operator)

    def login_no_perm(self):
        self.client.force_login(self.no_perm_user)

    def test_get_returns_404_without_invite_permission(self):
        self.login_no_perm()

        url = reverse(
            "ops_organization:create_admin_invitation",
            kwargs={"organization_id": self.org1.pk},
        )
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 404)

    def test_get_ok_and_shows_org_name_when_has_permission(self):
        self.login_operator()

        url = reverse(
            "ops_organization:create_admin_invitation",
            kwargs={"organization_id": self.org1.pk},
        )
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Org A")
        self.assertContains(resp, "招待")

    @patch("accounts.views.ops_organization_views.invite_organization_administrator")
    def test_post_valid_calls_service_and_redirects_to_detail(self, mock_invite):
        self.login_operator()

        url = reverse(
            "ops_organization:create_admin_invitation",
            kwargs={"organization_id": self.org1.pk},
        )
        resp = self.client.post(url, data={"email": "NewAdmin@example.com"})

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp["Location"],
            reverse("ops_organization:detail", kwargs={"pk": self.org1.pk}),
        )

        mock_invite.assert_called_once()
        called_kwargs = mock_invite.call_args.kwargs

        self.assertEqual(
            called_kwargs["accept_base_url"],
            "https://example.com"
            + reverse("ops_organization:accept_org_admin_invitation"),
        )
        self.assertEqual(called_kwargs["organization_id"], self.org1.pk)
        self.assertEqual(called_kwargs["email_address"], "NewAdmin@example.com")

        # request.user は SimpleLazyObject の場合があるため、
        # オブジェクト完全一致ではなく中身を確認する
        self.assertEqual(called_kwargs["user"].id, self.operator.id)
        self.assertEqual(called_kwargs["user"].email, self.operator.email)

    def test_post_invalid_email_rerenders_form(self):
        self.login_operator()

        url = reverse(
            "ops_organization:create_admin_invitation",
            kwargs={"organization_id": self.org1.pk},
        )
        resp = self.client.post(url, data={"email": "not-an-email"})

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "有効なメールアドレス")

    @patch(
        "accounts.views.ops_organization_views.invite_organization_administrator",
        side_effect=InvitationAlreadyExistsError("既に有効な招待が存在します。"),
    )
    def test_post_invitation_already_exists_rerenders_form_with_error(self, mock_invite):
        self.login_operator()

        url = reverse(
            "ops_organization:create_admin_invitation",
            kwargs={"organization_id": self.org1.pk},
        )
        resp = self.client.post(url, data={"email": "dup@example.com"})

        self.assertEqual(resp.status_code, 200)
        self.assertIn("email", resp.context["form"].errors)
        self.assertContains(resp, "すでに有効な招待が存在しています。")
        mock_invite.assert_called_once()

    @patch(
        "accounts.views.ops_organization_views.invite_organization_administrator",
        side_effect=ExistingUserWrongRoleError("すでに他の役職として当該組織に所属しています。"),
    )
    def test_post_existing_user_wrong_role_rerenders_form_with_email_error(self, mock_invite):
        self.login_operator()

        url = reverse(
            "ops_organization:create_admin_invitation",
            kwargs={"organization_id": self.org1.pk},
        )
        resp = self.client.post(url, data={"email": "existing@example.com"})

        self.assertEqual(resp.status_code, 200)
        self.assertIn("form", resp.context)
        self.assertIn("email", resp.context["form"].errors)
        self.assertContains(resp, "すでに組織に別の役職として登録されています。")
        mock_invite.assert_called_once()

    @patch(
        "accounts.views.ops_organization_views.invite_organization_administrator",
        side_effect=AnotherRoleExistsInAnotherOrganizationError("すでに他の役職として異なる組織に所属しています。"),
    )
    def test_post_another_role_in_another_org_rerenders_form_with_email_error(self, mock_invite):
        self.login_operator()

        url = reverse(
            "ops_organization:create_admin_invitation",
            kwargs={"organization_id": self.org1.pk},
        )
        resp = self.client.post(url, data={"email": "existing@example.com"})

        self.assertEqual(resp.status_code, 200)
        self.assertIn("form", resp.context)
        self.assertIn("email", resp.context["form"].errors)
        self.assertContains(resp, "すでに別組織において、異なる役職として登録されています。")
        mock_invite.assert_called_once()

    @patch(
        "accounts.views.ops_organization_views.invite_organization_administrator",
        side_effect=OrganizationAdministratorAlreadyAssignedError("すでに当該組織の組織管理者です。"),
    )
    def test_post_org_admin_already_assigned_redirects_to_detail_with_info_message(self, mock_invite):
        self.login_operator()

        url = reverse(
            "ops_organization:create_admin_invitation",
            kwargs={"organization_id": self.org1.pk},
        )
        resp = self.client.post(url, data={"email": "existing@example.com"}, follow=True)

        self.assertRedirects(
            resp,
            reverse("ops_organization:detail", kwargs={"pk": self.org1.pk}),
        )
        messages = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertIn("すでに当該組織の組織管理者です。", messages)
        mock_invite.assert_called_once()

    @patch(
        "accounts.views.ops_organization_views.invite_organization_administrator",
        side_effect=OrganizationAdministratorExistsInAnotherOrganizationError("他の組織の組織管理者です。"),
    )
    def test_post_org_admin_exists_in_another_org_redirects_to_detail_with_error_message(self, mock_invite):
        self.login_operator()

        url = reverse(
            "ops_organization:create_admin_invitation",
            kwargs={"organization_id": self.org1.pk},
        )
        resp = self.client.post(url, data={"email": "existing@example.com"}, follow=True)

        self.assertRedirects(
            resp,
            reverse("ops_organization:detail", kwargs={"pk": self.org1.pk}),
        )
        messages = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertIn(
            "すでに他の組織で組織管理者として登録されています。新規招待ではなく、割り当てをご利用ください。",
            messages,
        )
        mock_invite.assert_called_once()

    @patch(
        "accounts.views.ops_organization_views.invite_organization_administrator",
        side_effect=InvitationOrganizationNotFoundError("招待対象の組織が存在しません。"),
    )
    def test_post_org_not_found_redirects_to_list_with_error_message(self, mock_invite):
        self.login_operator()

        url = reverse(
            "ops_organization:create_admin_invitation",
            kwargs={"organization_id": self.org1.pk},
        )
        resp = self.client.post(url, data={"email": "existing@example.com"}, follow=True)

        self.assertRedirects(resp, reverse("ops_organization:list"))
        messages = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertIn(
            "対象の組織が見つからないため、招待を完了できませんでした。組織一覧から状態をご確認ください。",
            messages,
        )
        mock_invite.assert_called_once()

    @patch(
        "accounts.views.ops_organization_views.invite_organization_administrator",
        side_effect=Exception("boom"),
    )
    def test_post_unexpected_exception_redirects_to_detail_with_error_message(self, mock_invite):
        self.login_operator()

        url = reverse(
            "ops_organization:create_admin_invitation",
            kwargs={"organization_id": self.org1.pk},
        )
        resp = self.client.post(url, data={"email": "existing@example.com"}, follow=True)

        self.assertRedirects(
            resp,
            reverse("ops_organization:detail", kwargs={"pk": self.org1.pk}),
        )
        messages = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertIn("招待の送信に失敗しました。", messages)
        mock_invite.assert_called_once()

    def test_post_ignores_body_organization_id_and_uses_url_kwarg(self):
        self.login_operator()

        url = reverse(
            "ops_organization:create_admin_invitation",
            kwargs={"organization_id": self.org1.pk},
        )

        with patch("accounts.views.ops_organization_views.invite_organization_administrator") as mock_invite:
            self.client.post(
                url,
                data={
                    "email": "new@example.com",
                    "organization_id": self.org2.pk,
                },
            )

        called_kwargs = mock_invite.call_args.kwargs
        self.assertEqual(called_kwargs["organization_id"], self.org1.pk)

    def test_get_returns_404_when_org_does_not_exist(self):
        self.login_operator()

        url = reverse(
            "ops_organization:create_admin_invitation",
            kwargs={"organization_id": 999999},
        )
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 404)