from datetime import timedelta
from unittest.mock import patch

from django.core import signing
from django.test import TestCase
from django.utils import timezone

from accounts.models import Organization, OrganizationAdministrator, Invitation, InvitationRole
from accounts.services.accept_invitations import (
    load_invitation_id_from_token,
    get_acceptable_invitation_by_id,
    get_acceptable_invitation_by_token,
    build_accept_invitation_display_info,
    create_org_admin,
    check_and_confirm_invitation,
    get_invitation_for_acceptance_lock,
)
from accounts.services.exceptions import (
    InvalidTokenError,
    InvitationDoesNotExist,
    InactiveInvitationError,
    ExistingUserError,
)
from accounts.services.invitation_tokens import SALT


class AcceptInvitationsServiceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="テスト組織")

        self.inviter = OrganizationAdministrator(
            username="招待者",
            email="inviter@example.com",
        )
        self.inviter.set_password("inviter-pass-123")
        self.inviter.save()
        self.inviter.organizations.add(self.organization)

    def _create_invitation(
        self,
        *,
        email="invitee@example.com",
        role=InvitationRole.ORG_ADMIN,
        expires_at=None,
        used_at=None,
        revoked_at=None,
    ) -> Invitation:
        invitation = Invitation.objects.create(
            organization=self.organization,
            email=email,
            role=role,
            expires_at=expires_at or (timezone.now() + timedelta(days=3)),
            invited_by=self.inviter,
        )

        if used_at is not None:
            invitation.used_at = used_at
        if revoked_at is not None:
            invitation.revoked_at = revoked_at

        if used_at is not None or revoked_at is not None:
            invitation.save(update_fields=["used_at", "revoked_at"])

        return invitation

    def _build_token(self, *, invitation_id: int) -> str:
        return signing.dumps(
            {"invitation_id": invitation_id},
            salt=SALT,
        )

    # ----------------------------
    # load_invitation_id_from_token
    # ----------------------------

    def test_load_invitation_id_from_token_returns_invitation_id(self):
        invitation = self._create_invitation()
        token = self._build_token(invitation_id=invitation.id)

        actual = load_invitation_id_from_token(token=token)

        self.assertEqual(actual, invitation.id)

    def test_load_invitation_id_from_token_raises_when_token_is_invalid(self):
        with self.assertRaises(InvalidTokenError):
            load_invitation_id_from_token(token="not-a-valid-token")

    @patch("accounts.services.accept_invitations.signing.loads")
    def test_load_invitation_id_from_token_raises_when_payload_is_not_dict(self, mock_loads):
        mock_loads.return_value = "not-dict"

        with self.assertRaises(InvalidTokenError):
            load_invitation_id_from_token(token="dummy-token")

    @patch("accounts.services.accept_invitations.signing.loads")
    def test_load_invitation_id_from_token_raises_when_invitation_id_is_missing(self, mock_loads):
        mock_loads.return_value = {"wrong_key": 123}

        with self.assertRaises(InvalidTokenError):
            load_invitation_id_from_token(token="dummy-token")

    @patch("accounts.services.accept_invitations.signing.loads")
    def test_load_invitation_id_from_token_raises_when_invitation_id_is_not_int(self, mock_loads):
        mock_loads.return_value = {"invitation_id": "abc"}

        with self.assertRaises(InvalidTokenError):
            load_invitation_id_from_token(token="dummy-token")

    @patch("accounts.services.accept_invitations.signing.loads")
    def test_load_invitation_id_from_token_raises_when_invitation_id_is_zero_or_less(self, mock_loads):
        mock_loads.return_value = {"invitation_id": 0}

        with self.assertRaises(InvalidTokenError):
            load_invitation_id_from_token(token="dummy-token")

    # ----------------------------
    # get_acceptable_invitation_by_id
    # ----------------------------

    def test_get_acceptable_invitation_by_id_returns_invitation_when_active(self):
        invitation = self._create_invitation()

        actual = get_acceptable_invitation_by_id(invitation_id=invitation.id)

        self.assertEqual(actual.id, invitation.id)
        self.assertEqual(actual.organization.id, self.organization.id)

    def test_get_acceptable_invitation_by_id_raises_when_not_found(self):
        with self.assertRaises(InvitationDoesNotExist):
            get_acceptable_invitation_by_id(invitation_id=999999)

    def test_get_acceptable_invitation_by_id_raises_when_used(self):
        invitation = self._create_invitation(
            used_at=timezone.now(),
        )

        with self.assertRaises(InactiveInvitationError):
            get_acceptable_invitation_by_id(invitation_id=invitation.id)

    def test_get_acceptable_invitation_by_id_raises_when_revoked(self):
        invitation = self._create_invitation(
            revoked_at=timezone.now(),
        )

        with self.assertRaises(InactiveInvitationError):
            get_acceptable_invitation_by_id(invitation_id=invitation.id)

    def test_get_acceptable_invitation_by_id_raises_when_expired(self):
        invitation = self._create_invitation(
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        with self.assertRaises(InactiveInvitationError):
            get_acceptable_invitation_by_id(invitation_id=invitation.id)

    # ----------------------------
    # get_acceptable_invitation_by_token
    # ----------------------------

    def test_get_acceptable_invitation_by_token_returns_invitation(self):
        invitation = self._create_invitation()
        token = self._build_token(invitation_id=invitation.id)

        actual = get_acceptable_invitation_by_token(token=token)

        self.assertEqual(actual.id, invitation.id)

    # ----------------------------
    # build_accept_invitation_display_info
    # ----------------------------

    def test_build_accept_invitation_display_info_returns_display_info(self):
        invitation = self._create_invitation(
            email="DISPLAY@example.com",
            role=InvitationRole.ORG_ADMIN,
        )
        token = self._build_token(invitation_id=invitation.id)

        actual = build_accept_invitation_display_info(token=token)

        self.assertEqual(actual.organization_name, self.organization.name)
        self.assertEqual(actual.email, "display@example.com")
        self.assertEqual(actual.role, InvitationRole.ORG_ADMIN)

    # ----------------------------
    # create_org_admin
    # ----------------------------

    def test_create_org_admin_creates_user_with_hashed_password_and_organization(self):
        user = create_org_admin(
            username="受理ユーザー",
            email="new-admin@example.com",
            password="test-password-123",
            organization=self.organization,
        )

        self.assertIsInstance(user, OrganizationAdministrator)
        self.assertEqual(user.email, "new-admin@example.com")
        self.assertEqual(user.role, "organization_administrator")
        self.assertTrue(user.check_password("test-password-123"))
        self.assertTrue(user.organizations.filter(id=self.organization.id).exists())
        self.assertFalse(user.is_first_login)

    # ----------------------------
    # get_invitation_for_acceptance_lock
    # ----------------------------

    def test_get_invitation_for_acceptance_lock_returns_invitation(self):
        invitation = self._create_invitation()

        actual = get_invitation_for_acceptance_lock(invitation_id=invitation.id)

        self.assertEqual(actual.id, invitation.id)
        self.assertEqual(actual.organization.id, self.organization.id)

    # ----------------------------
    # check_and_confirm_invitation
    # ----------------------------

    def test_check_and_confirm_invitation_creates_org_admin_and_marks_invitation_used(self):
        invitation = self._create_invitation(
            email="accepted-user@example.com",
            role=InvitationRole.ORG_ADMIN,
        )
        token = self._build_token(invitation_id=invitation.id)

        user = check_and_confirm_invitation(
            token=token,
            username="受理された管理者",
            password="strong-password-123",
        )

        invitation.refresh_from_db()
        user.refresh_from_db()

        self.assertIsInstance(user, OrganizationAdministrator)
        self.assertEqual(user.email, "accepted-user@example.com")
        self.assertEqual(user.username, "受理された管理者")
        self.assertTrue(user.check_password("strong-password-123"))
        self.assertTrue(user.organizations.filter(id=self.organization.id).exists())
        self.assertIsNotNone(invitation.used_at)

    def test_check_and_confirm_invitation_raises_when_existing_user_already_exists(self):
        invitation = self._create_invitation(
            email="already-exists@example.com",
            role=InvitationRole.ORG_ADMIN,
        )
        token = self._build_token(invitation_id=invitation.id)

        existing_user = OrganizationAdministrator(
            username="既存ユーザー",
            email="already-exists@example.com",
        )
        existing_user.set_password("existing-password-123")
        existing_user.save()

        with self.assertRaises(ExistingUserError):
            check_and_confirm_invitation(
                token=token,
                username="新しい名前",
                password="new-password-123",
            )

        invitation.refresh_from_db()
        self.assertIsNone(invitation.used_at)

    def test_check_and_confirm_invitation_raises_when_invitation_is_already_used_before_confirmation(self):
        invitation = self._create_invitation(
            email="used-before-confirm@example.com",
            role=InvitationRole.ORG_ADMIN,
        )
        token = self._build_token(invitation_id=invitation.id)

        invitation.mark_used()

        with self.assertRaises(InactiveInvitationError):
            check_and_confirm_invitation(
                token=token,
                username="受理ユーザー",
                password="test-password-123",
            )

    def test_check_and_confirm_invitation_raises_when_role_is_not_supported(self):
        invitation = self._create_invitation(
            email="teacher-like@example.com",
            role=InvitationRole.TEACHER,
        )
        token = self._build_token(invitation_id=invitation.id)

        with self.assertRaises(InactiveInvitationError):
            check_and_confirm_invitation(
                token=token,
                username="未対応ロール",
                password="test-password-123",
            )

        invitation.refresh_from_db()
        self.assertIsNone(invitation.used_at)

    def test_check_and_confirm_invitation_raises_when_token_is_invalid(self):
        with self.assertRaises(InvalidTokenError):
            check_and_confirm_invitation(
                token="invalid-token",
                username="受理ユーザー",
                password="test-password-123",
            )

    def test_org_admin_created_with_is_first_login_false(self):
        """
        招待経由で作成された組織管理者は初回ログイン扱いにならない
        """
        invitation = self._create_invitation(role=InvitationRole.ORG_ADMIN)
        token = self._build_token(invitation_id=invitation.id)

        user = check_and_confirm_invitation(
            token=token,
            username="新規管理者",
            password="test-password-123",
        )

        user.refresh_from_db()
        self.assertFalse(user.is_first_login)

    @patch("accounts.services.accept_invitations.get_invitation_for_acceptance_lock")
    def test_check_and_confirm_invitation_raises_when_invitation_becomes_inactive_after_lock(
        self,
        mock_get_locked_invitation,
    ):
        """
        初回確認後からロック取得までの間に招待が無効化された場合、
        ユーザーを作成しない
        """
        invitation = self._create_invitation(
            email="race-condition@example.com",
            role=InvitationRole.ORG_ADMIN,
        )
        token = self._build_token(invitation_id=invitation.id)

        invitation.used_at = timezone.now()
        mock_get_locked_invitation.return_value = invitation

        before_count = OrganizationAdministrator.objects.count()

        with self.assertRaises(InactiveInvitationError):
            check_and_confirm_invitation(
                token=token,
                username="競合ユーザー",
                password="test-password-123",
            )

        self.assertEqual(
            OrganizationAdministrator.objects.count(),
            before_count,
        )

    @patch("accounts.services.accept_invitations.signing.loads")
    def test_load_invitation_id_from_token_raises_when_signature_is_expired(
        self,
        mock_loads,
    ):
        mock_loads.side_effect = signing.SignatureExpired("expired")

        with self.assertRaises(InvalidTokenError):
            load_invitation_id_from_token(token="expired-token")
