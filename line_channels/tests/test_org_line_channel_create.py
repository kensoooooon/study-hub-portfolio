# line_channels/tests/test_org_line_channel_create.py
from __future__ import annotations

from unittest.mock import Mock, patch

import requests

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import NoReverseMatch, reverse


def _setup_ops_group() -> Group:
    """
    ops_line_channels グループを必ず作った上で返す。
    グループ権限運用にしたため、テストDBでも毎回これを通すのが安全。
    """
    call_command("setup_ops_groups")
    return Group.objects.get(name="ops_line_channels")


class OrgLineChannelCreateFlowTests(TestCase):
    """
    OrganizationLineChannelCreateView の作成フロー一式をテストする

    カバー範囲：
    - 権限が無い場合は 404 マスク
    - GET 正常表示
    - POST 正常作成（LINE bot/info を叩き bot_user_id を取得→DB作成→store_secret 2回）
    - 既に登録済みの場合は作成せず detail へリダイレクト
    - LINE API が 401/403/500 等で失敗した場合、フォームエラーとして同画面に戻る
    - bot_user_id が既存と衝突した場合（uq_org_bot_user_id）、フォームエラーとして同画面に戻る
    - store_secret が失敗した場合、atomic により LineChannel が残らない（ロールバック）
    """

    @classmethod
    def setUpTestData(cls):
        cls.Organization = apps.get_model("accounts", "Organization")
        cls.LineChannel = apps.get_model("line_channels", "LineChannel")

        cls.org = cls.Organization.objects.create(name="Test Org")

        User = get_user_model()
        cls.user_no_perm = User.objects.create_user(
            email="no_perm@example.com",
            password="pass12345",
            role="organization_administrator",
            username="No Perm",
        )
        cls.user_with_perm = User.objects.create_user(
            email="with_perm@example.com",
            password="pass12345",
            role="organization_administrator",
            username="With Perm",
        )

        # OrganizationAdministrator がいるプロジェクトでは、そちらを優先
        try:
            OrgAdminModel = apps.get_model("accounts", "OrganizationAdministrator")
            cls.org_admin = OrgAdminModel.objects.create_user(
                email="org_admin@example.com",
                password="pass12345",
                role="organization_administrator",
                username="Org Admin",
            )
            cls.org_admin.organizations.add(cls.org)
            cls.user_with_perm = cls.org_admin
        except LookupError:
            pass

        # グループ運用：ops_line_channels に入れる（= add_linechannel 等もグループ経由でTrue）
        g = _setup_ops_group()
        cls.user_with_perm.groups.add(g)

    # -------------------------
    # helpers
    # -------------------------
    def _create_url(self) -> str:
        candidates = [
            ("ops_organization:org_line_channels:org_new", [self.org.pk]),
            ("ops_organization:line_channels:org_new", [self.org.pk]),
            ("org_line_channels:org_new", [self.org.pk]),
        ]
        last_err = None
        for name, args in candidates:
            try:
                return reverse(name, args=args)
            except NoReverseMatch as e:
                last_err = e

        # fallback（プロジェクト側URLが変わったときの保険）
        if last_err:
            return f"/accounts/ops_organization/organizations/{self.org.pk}/line-channels/new/"
        raise last_err  # pragma: no cover

    def _post_payload(self, *, channel_id="1234567890") -> dict:
        return {
            "channel_id": channel_id,
            "channel_secret": "A" * 30,
            "channel_secret_confirm": "A" * 30,
            "channel_access_token": "B" * 80,
            "channel_access_token_confirm": "B" * 80,
        }

    # -------------------------
    # tests
    # -------------------------
    def test_get_denied_without_permission_is_404_mask(self):
        self.client.force_login(self.user_no_perm)
        resp = self.client.get(self._create_url())
        self.assertEqual(resp.status_code, 404)

    def test_get_ok_with_permission(self):
        self.client.force_login(self.user_with_perm)
        resp = self.client.get(self._create_url())
        self.assertEqual(resp.status_code, 200)

        self.assertContains(resp, 'name="channel_id"')
        self.assertContains(resp, 'name="channel_secret"')
        self.assertContains(resp, 'name="channel_access_token"')

    @patch("line_channels.views.store_secret")
    @patch("line_channels.views.requests.get")
    def test_post_success_creates_channel_and_redirects(self, m_get, m_store_secret):
        self.client.force_login(self.user_with_perm)

        mock_resp = Mock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"userId": "U_TEST_BOT"}
        m_get.return_value = mock_resp

        resp = self.client.post(self._create_url(), data=self._post_payload(), follow=False)
        self.assertEqual(resp.status_code, 302)

        qs = self.LineChannel.objects.filter(organization=self.org, channel_id="1234567890")
        self.assertEqual(qs.count(), 1)

        self.assertEqual(m_store_secret.call_count, 2)

    @patch("line_channels.views.store_secret")
    @patch("line_channels.views.requests.get")
    def test_post_duplicate_channel_does_not_store_secret(self, m_get, m_store_secret):
        self.LineChannel.objects.create(
            organization=self.org,
            channel_id="1234567890",
            bot_user_id="U_EXISTING",
            is_active=True,
        )

        self.client.force_login(self.user_with_perm)

        mock_resp = Mock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"userId": "U_FROM_LINE"}
        m_get.return_value = mock_resp

        resp = self.client.post(self._create_url(), data=self._post_payload(), follow=False)
        self.assertEqual(resp.status_code, 302)

        self.assertEqual(
            self.LineChannel.objects.filter(organization=self.org, channel_id="1234567890").count(),
            1,
        )
        m_store_secret.assert_not_called()

    @patch("line_channels.views.store_secret")
    @patch("line_channels.views.requests.get")
    def test_post_line_api_401_results_in_form_error(self, m_get, m_store_secret):
        self.client.force_login(self.user_with_perm)

        err_resp = Mock(status_code=401)
        http_err = requests.HTTPError()
        http_err.response = err_resp

        mock_resp = Mock()
        mock_resp.raise_for_status.side_effect = http_err
        m_get.return_value = mock_resp

        resp = self.client.post(self._create_url(), data=self._post_payload(), follow=False)
        self.assertEqual(resp.status_code, 200)

        self.assertContains(resp, "アクセストークンが無効")

        m_store_secret.assert_not_called()
        self.assertEqual(self.LineChannel.objects.filter(organization=self.org).count(), 0)

    @patch("line_channels.views.requests.get")
    def test_post_bot_user_id_conflict_returns_form_error(self, m_get):
        self.LineChannel.objects.create(
            organization=self.org,
            channel_id="1111111111",
            bot_user_id="U_SAME",
            is_active=True,
        )

        self.client.force_login(self.user_with_perm)

        mock_resp = Mock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"userId": "U_SAME"}
        m_get.return_value = mock_resp

        resp = self.client.post(
            self._create_url(),
            data=self._post_payload(channel_id="2222222222"),
            follow=False,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "このアクセストークンは、すでに別のチャネルIDで登録されています")
        self.assertEqual(self.LineChannel.objects.filter(organization=self.org).count(), 1)

    @patch("line_channels.views.store_secret")
    @patch("line_channels.views.requests.get")
    def test_post_store_secret_failure_rolls_back_channel(self, m_get, m_store_secret):
        self.client.force_login(self.user_with_perm)

        mock_resp = Mock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"userId": "U_TEST_BOT"}
        m_get.return_value = mock_resp

        m_store_secret.side_effect = RuntimeError("boom")

        resp = self.client.post(self._create_url(), data=self._post_payload(), follow=False)
        self.assertEqual(resp.status_code, 302)

        # atomic が効いていれば作成されない
        self.assertEqual(self.LineChannel.objects.filter(organization=self.org).count(), 0)

    @patch("line_channels.views.store_secret")
    @patch("line_channels.views.requests.get")
    def test_post_success_store_secret_called_with_expected_args(self, m_get, m_store_secret):
        from line_channels.models import KeyKind

        self.client.force_login(self.user_with_perm)

        mock_resp = Mock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"userId": "U_TEST_BOT"}
        m_get.return_value = mock_resp

        payload = self._post_payload(channel_id="3333333333")
        resp = self.client.post(self._create_url(), data=payload, follow=False)
        self.assertEqual(resp.status_code, 302)

        ch = self.LineChannel.objects.get(organization=self.org, channel_id="3333333333")

        expected_secret = payload["channel_secret"].encode("utf-8")
        expected_token = payload["channel_access_token"].encode("utf-8")

        self.assertEqual(m_store_secret.call_count, 2)
        first_args, _ = m_store_secret.call_args_list[0]
        second_args, _ = m_store_secret.call_args_list[1]

        self.assertEqual(first_args[0], ch)
        self.assertEqual(first_args[1], KeyKind.CHANNEL_SECRET)
        self.assertEqual(first_args[2], expected_secret)

        self.assertEqual(second_args[0], ch)
        self.assertEqual(second_args[1], KeyKind.ACCESS_TOKEN)
        self.assertEqual(second_args[2], expected_token)

    @patch("line_channels.views.store_secret")
    @patch("line_channels.views.requests.get")
    def test_post_line_api_returns_json_without_userid_is_form_error(self, m_get, m_store_secret):
        self.client.force_login(self.user_with_perm)

        mock_resp = Mock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {}
        m_get.return_value = mock_resp

        resp = self.client.post(self._create_url(), data=self._post_payload(channel_id="4444444444"), follow=False)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "LINE APIの応答が想定外")
        m_store_secret.assert_not_called()
        self.assertEqual(self.LineChannel.objects.filter(organization=self.org).count(), 0)

    @patch("line_channels.views.store_secret")
    @patch("line_channels.views.requests.get")
    def test_post_line_api_json_value_error_is_form_error(self, m_get, m_store_secret):
        self.client.force_login(self.user_with_perm)

        mock_resp = Mock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.side_effect = ValueError("invalid json")
        m_get.return_value = mock_resp

        resp = self.client.post(self._create_url(), data=self._post_payload(channel_id="5555555555"), follow=False)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "LINE APIの応答が想定外")
        m_store_secret.assert_not_called()
        self.assertEqual(self.LineChannel.objects.filter(organization=self.org).count(), 0)

    @patch("line_channels.views.store_secret")
    @patch("line_channels.views.requests.get")
    def test_post_line_api_request_exception_is_form_error(self, m_get, m_store_secret):
        from requests.exceptions import RequestException

        self.client.force_login(self.user_with_perm)

        m_get.side_effect = RequestException("timeout")

        resp = self.client.post(self._create_url(), data=self._post_payload(channel_id="6666666666"), follow=False)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "LINE APIへの接続でエラー")
        m_store_secret.assert_not_called()
        self.assertEqual(self.LineChannel.objects.filter(organization=self.org).count(), 0)


class ChannelAccessTokenRotateViewTests(TestCase):
    """
    ChannelAccessTokenRotateView のUX改善（例外時にform_invalidで指し戻す）をテスト
    """

    @classmethod
    def setUpTestData(cls):
        cls.Organization = apps.get_model("accounts", "Organization")
        cls.LineChannel = apps.get_model("line_channels", "LineChannel")
        cls.org = cls.Organization.objects.create(name="Test Org")

        User = get_user_model()
        cls.user_no_perm = User.objects.create_user(
            email="no_perm_rotate@example.com",
            password="pass12345",
            role="organization_administrator",
            username="No Perm Rotate",
        )
        cls.user_with_perm = User.objects.create_user(
            email="with_perm_rotate@example.com",
            password="pass12345",
            role="organization_administrator",
            username="With Perm Rotate",
        )

        # グループ運用
        g = _setup_ops_group()
        cls.user_with_perm.groups.add(g)

        cls.channel = cls.LineChannel.objects.create(
            organization=cls.org,
            channel_id="9990001111",
            bot_user_id="U_ROTATE",
            is_active=True,
        )

    def _rotate_url(self) -> str:
        return reverse("line_channels:rotate_channel_access_token", args=[self.channel.pk])

    def _post_payload(self, token="B" * 80, confirm="B" * 80) -> dict:
        return {
            "new_channel_access_token": token,
            "new_channel_access_token_confirm": confirm,
        }

    def test_get_denied_without_permission_is_404_mask(self):
        self.client.force_login(self.user_no_perm)
        resp = self.client.get(self._rotate_url())
        self.assertEqual(resp.status_code, 404)

    def test_get_ok_with_permission(self):
        self.client.force_login(self.user_with_perm)
        resp = self.client.get(self._rotate_url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="new_channel_access_token"')
        self.assertContains(resp, 'name="new_channel_access_token_confirm"')

    @patch("line_channels.views.store_secret")
    def test_post_success_redirects_to_detail(self, m_store_secret):
        self.client.force_login(self.user_with_perm)
        resp = self.client.post(self._rotate_url(), data=self._post_payload(), follow=False)
        self.assertEqual(resp.status_code, 302)
        m_store_secret.assert_called_once()

    @patch("line_channels.views.store_secret")
    def test_post_store_secret_failure_returns_form_invalid(self, m_store_secret):
        self.client.force_login(self.user_with_perm)
        m_store_secret.side_effect = RuntimeError("boom")

        resp = self.client.post(self._rotate_url(), data=self._post_payload(), follow=False)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "チャンネルアクセストークン登録に失敗しました。")
        m_store_secret.assert_called_once()

    @patch("line_channels.views.store_secret")
    def test_post_confirm_mismatch_is_form_error_and_does_not_call_store_secret(self, m_store_secret):
        self.client.force_login(self.user_with_perm)

        resp = self.client.post(
            self._rotate_url(),
            data=self._post_payload(token="B" * 80, confirm="C" * 80),
            follow=False,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "確認用の入力が一致しません。")
        m_store_secret.assert_not_called()