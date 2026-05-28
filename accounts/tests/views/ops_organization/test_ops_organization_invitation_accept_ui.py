from __future__ import annotations

from collections import namedtuple
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.services.exceptions import (
    ExistingUserError,
    InactiveInvitationError,
    InvitationDoesNotExist,
    InvalidTokenError,
)


DisplayInfo = namedtuple(
    "DisplayInfo",
    ["organization_name", "email", "role"],
)


class OpsOrganizationInvitationAcceptUITests(TestCase):
    def _url(self):
        return reverse("ops_organization:accept_org_admin_invitation")

    def _valid_form_data(self, *, token: str = "valid-token"):
        return {
            "username": "new_admin",
            "password": "testpass123",
            "password_confirm": "testpass123",
            "t": token,
        }

    @patch("accounts.views.ops_organization_views.build_accept_invitation_display_info")
    def test_get_valid_token_renders_input_page_with_info(self, mock_build_info):
        mock_build_info.return_value = DisplayInfo(
            organization_name="Org A",
            email="invitee@example.com",
            role="organization_administrator",
        )

        resp = self.client.get(self._url(), data={"t": "valid-token"})

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "accounts/ops_organization/input.html")
        self.assertContains(resp, "組織管理者招待の受理")
        self.assertContains(resp, "Org A")
        self.assertContains(resp, "invitee@example.com")
        self.assertContains(resp, 'name="t" value="valid-token"', html=False)

        self.assertIn("token", resp.context)
        self.assertEqual(resp.context["token"], "valid-token")
        self.assertIn("info", resp.context)
        self.assertEqual(resp.context["info"].organization_name, "Org A")

        mock_build_info.assert_called_once_with(token="valid-token")

    def test_get_without_token_renders_invalid_page(self):
        resp = self.client.get(self._url())

        self.assertEqual(resp.status_code, 400)
        self.assertTemplateUsed(
            resp,
            "accounts/ops_organization/invalid_invitation.html",
        )
        self.assertContains(resp, "招待リンクを利用できません", status_code=400)
        self.assertContains(resp, "無効な招待リンクです。", status_code=400)

    @patch(
        "accounts.views.ops_organization_views.build_accept_invitation_display_info",
        side_effect=InvalidTokenError("不正なトークンです。"),
    )
    def test_get_invalid_token_renders_invalid_page(self, mock_build_info):
        resp = self.client.get(self._url(), data={"t": "bad-token"})

        self.assertEqual(resp.status_code, 400)
        self.assertTemplateUsed(
            resp,
            "accounts/ops_organization/invalid_invitation.html",
        )
        self.assertContains(resp, "招待リンクを利用できません", status_code=400)
        self.assertContains(resp, "不正なトークンです。", status_code=400)

        mock_build_info.assert_called_once_with(token="bad-token")

    @patch(
        "accounts.views.ops_organization_views.build_accept_invitation_display_info",
        side_effect=InvitationDoesNotExist("無効な招待です。"),
    )
    def test_get_nonexistent_invitation_renders_invalid_page(self, mock_build_info):
        resp = self.client.get(self._url(), data={"t": "missing-token"})

        self.assertEqual(resp.status_code, 400)
        self.assertTemplateUsed(
            resp,
            "accounts/ops_organization/invalid_invitation.html",
        )
        self.assertContains(resp, "招待リンクを利用できません", status_code=400)
        self.assertContains(resp, "無効な招待です。", status_code=400)

        mock_build_info.assert_called_once_with(token="missing-token")

    @patch(
        "accounts.views.ops_organization_views.build_accept_invitation_display_info",
        side_effect=InactiveInvitationError("無効な招待です。"),
    )
    def test_get_inactive_invitation_renders_invalid_page(self, mock_build_info):
        resp = self.client.get(self._url(), data={"t": "inactive-token"})

        self.assertEqual(resp.status_code, 400)
        self.assertTemplateUsed(
            resp,
            "accounts/ops_organization/invalid_invitation.html",
        )
        self.assertContains(resp, "招待リンクを利用できません", status_code=400)
        self.assertContains(resp, "無効な招待です。", status_code=400)

        mock_build_info.assert_called_once_with(token="inactive-token")

    @patch("accounts.views.ops_organization_views.check_and_confirm_invitation")
    def test_post_valid_calls_service_and_redirects_to_login(self, mock_confirm):
        resp = self.client.post(
            self._url(),
            data=self._valid_form_data(token="valid-token"),
        )

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("accounts_auth:login"))

        mock_confirm.assert_called_once_with(
            token="valid-token",
            username="new_admin",
            password="testpass123",
        )

    def test_post_without_token_renders_invalid_page(self):
        data = self._valid_form_data()
        data.pop("t")

        resp = self.client.post(self._url(), data=data)

        self.assertEqual(resp.status_code, 400)
        self.assertTemplateUsed(
            resp,
            "accounts/ops_organization/invalid_invitation.html",
        )
        self.assertContains(resp, "招待リンクを利用できません", status_code=400)
        self.assertContains(resp, "無効な招待リンクです。", status_code=400)

    @patch("accounts.views.ops_organization_views.build_accept_invitation_display_info")
    @patch(
        "accounts.views.ops_organization_views.check_and_confirm_invitation",
        side_effect=ExistingUserError("このメールアドレスはすでに利用されています。"),
    )
    def test_post_existing_user_rerenders_form_with_non_field_error(
        self,
        mock_confirm,
        mock_build_info,
    ):
        mock_build_info.return_value = DisplayInfo(
            organization_name="Org A",
            email="invitee@example.com",
            role="organization_administrator",
        )

        resp = self.client.post(
            self._url(),
            data=self._valid_form_data(token="valid-token"),
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "accounts/ops_organization/input.html")
        self.assertContains(resp, "このメールアドレスはすでに利用されています。")
        self.assertContains(resp, "Org A")
        self.assertContains(resp, "invitee@example.com")
        self.assertContains(resp, 'name="t" value="valid-token"', html=False)

        mock_confirm.assert_called_once_with(
            token="valid-token",
            username="new_admin",
            password="testpass123",
        )
        mock_build_info.assert_called_once_with(token="valid-token")

    @patch(
        "accounts.views.ops_organization_views.check_and_confirm_invitation",
        side_effect=InvalidTokenError("不正なトークンです。"),
    )
    def test_post_invalid_token_renders_invalid_page(self, mock_confirm):
        resp = self.client.post(
            self._url(),
            data=self._valid_form_data(token="bad-token"),
        )

        self.assertEqual(resp.status_code, 400)
        self.assertTemplateUsed(
            resp,
            "accounts/ops_organization/invalid_invitation.html",
        )
        self.assertContains(resp, "招待リンクを利用できません", status_code=400)
        self.assertContains(resp, "不正なトークンです。", status_code=400)

        mock_confirm.assert_called_once_with(
            token="bad-token",
            username="new_admin",
            password="testpass123",
        )

    @patch(
        "accounts.views.ops_organization_views.check_and_confirm_invitation",
        side_effect=InvitationDoesNotExist("無効な招待です。"),
    )
    def test_post_nonexistent_invitation_renders_invalid_page(self, mock_confirm):
        resp = self.client.post(
            self._url(),
            data=self._valid_form_data(token="missing-token"),
        )

        self.assertEqual(resp.status_code, 400)
        self.assertTemplateUsed(
            resp,
            "accounts/ops_organization/invalid_invitation.html",
        )
        self.assertContains(resp, "招待リンクを利用できません", status_code=400)
        self.assertContains(resp, "無効な招待です。", status_code=400)

        mock_confirm.assert_called_once_with(
            token="missing-token",
            username="new_admin",
            password="testpass123",
        )

    @patch(
        "accounts.views.ops_organization_views.check_and_confirm_invitation",
        side_effect=InactiveInvitationError("無効な招待です。"),
    )
    def test_post_inactive_invitation_renders_invalid_page(self, mock_confirm):
        resp = self.client.post(
            self._url(),
            data=self._valid_form_data(token="inactive-token"),
        )

        self.assertEqual(resp.status_code, 400)
        self.assertTemplateUsed(
            resp,
            "accounts/ops_organization/invalid_invitation.html",
        )
        self.assertContains(resp, "招待リンクを利用できません", status_code=400)
        self.assertContains(resp, "無効な招待です。", status_code=400)

        mock_confirm.assert_called_once_with(
            token="inactive-token",
            username="new_admin",
            password="testpass123",
        )

    @patch("accounts.views.ops_organization_views.build_accept_invitation_display_info")
    def test_post_form_invalid_keeps_info_in_context(self, mock_build_info):
        mock_build_info.return_value = DisplayInfo(
            organization_name="Org A",
            email="invitee@example.com",
            role="organization_administrator",
        )

        resp = self.client.post(
            self._url(),
            data={
                "username": "new_admin",
                "password": "testpass123",
                "password_confirm": "different-password",
                "t": "valid-token",
            },
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "accounts/ops_organization/input.html")
        self.assertIn("info", resp.context)
        self.assertEqual(resp.context["info"].organization_name, "Org A")
        self.assertContains(resp, "Org A")
        self.assertContains(resp, "invitee@example.com")
        mock_build_info.assert_called_once_with(token="valid-token")