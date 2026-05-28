# accounts/tests/test_invitation_models.py
from __future__ import annotations

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import Organization, BaseUser
from accounts.models.invitation_models import Invitation, InvitationRole, SendStatus



class InvitationConstraintTests(TestCase):
    def setUp(self) -> None:
        self.org = Organization.objects.create(name="Test Org")
        self.inviter = BaseUser.objects.create_user(
            email="ops@example.com",
            password="password",
            role="organization_administrator",
            username="Ops User",
        )

    def test_unique_active_invitation_per_organization_and_email(self):
        """
        同一 (organization, email) で
        used_at IS NULL かつ revoked_at IS NULL の招待は 1件に制限されること
        """
        expires_at = timezone.now() + timedelta(days=2)
        email = "invitee@example.com"

        Invitation.objects.create(
            organization=self.org,
            email=email,
            role=InvitationRole.ORG_ADMIN,
            expires_at=expires_at,
            invited_by=self.inviter,
        )

        # まだ未使用・未失効の同じ (org, email) をもう1件作ろうとすると制約違反
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Invitation.objects.create(
                    organization=self.org,
                    email=email,
                    role=InvitationRole.ORG_ADMIN,
                    expires_at=expires_at,
                    invited_by=self.inviter,
                )

    def test_can_create_new_invitation_after_revoked(self):
        """
        既存招待が revoked になれば、新しい招待を同一 (org, email) で発行できること
        """
        expires_at = timezone.now() + timedelta(days=2)
        email = "invitee2@example.com"

        inv = Invitation.objects.create(
            organization=self.org,
            email=email,
            role=InvitationRole.ORG_ADMIN,
            expires_at=expires_at,
            invited_by=self.inviter,
        )

        # 旧招待を失効（手動取り消し）
        inv.revoked_at = timezone.now()
        inv.save(update_fields=["revoked_at"])

        # 新しい招待を発行できる
        Invitation.objects.create(
            organization=self.org,
            email=email,
            role=InvitationRole.ORG_ADMIN,
            expires_at=expires_at,
            invited_by=self.inviter,
        )

    def test_can_create_new_invitation_after_used(self):
        """
        既存招待が used になれば、新しい招待を同一 (org, email) で発行できること
        """
        expires_at = timezone.now() + timedelta(days=2)
        email = "invitee3@example.com"

        inv = Invitation.objects.create(
            organization=self.org,
            email=email,
            role=InvitationRole.ORG_ADMIN,
            expires_at=expires_at,
            invited_by=self.inviter,
        )

        # 旧招待を消費（受諾済み）
        inv.used_at = timezone.now()
        inv.save(update_fields=["used_at"])

        # 新しい招待を発行できる
        Invitation.objects.create(
            organization=self.org,
            email=email,
            role=InvitationRole.ORG_ADMIN,
            expires_at=expires_at,
            invited_by=self.inviter,
        )
    

class InvitationModelTests(TestCase):
    def setUp(self) -> None:
        self.org = Organization.objects.create(name="Test Org")
        self.inviter = BaseUser.objects.create_user(
            email="ops2@example.com",
            password="password",
            role="organization_administrator",
            username="Ops User 2",
        )

    def _make_invitation(self, **kwargs):
        defaults = {
            "organization": self.org,
            "email": "invitee@example.com",
            "role": InvitationRole.ORG_ADMIN,
            "expires_at": timezone.now() + timedelta(days=1),
            "invited_by": self.inviter,
        }
        defaults.update(kwargs)
        return Invitation.objects.create(**defaults)

    def test_is_active_true_for_unused_unrevoked_unexpired_invitation(self):
        invitation = self._make_invitation()
        self.assertTrue(invitation.is_active)

    def test_is_active_false_when_used(self):
        invitation = self._make_invitation(used_at=timezone.now())
        self.assertFalse(invitation.is_active)

    def test_is_active_false_when_revoked(self):
        invitation = self._make_invitation(revoked_at=timezone.now())
        self.assertFalse(invitation.is_active)

    def test_is_active_false_when_expired(self):
        invitation = self._make_invitation(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertFalse(invitation.is_active)

    def test_revoke_sets_revoked_at(self):
        invitation = self._make_invitation()
        now = timezone.now()

        invitation.revoke(at=now)
        invitation.refresh_from_db()

        self.assertEqual(invitation.revoked_at, now)

    def test_revoke_is_idempotent(self):
        invitation = self._make_invitation()
        first = timezone.now()
        second = first + timedelta(minutes=5)

        invitation.revoke(at=first)
        invitation.revoke(at=second)
        invitation.refresh_from_db()

        self.assertEqual(invitation.revoked_at, first)

    def test_mark_used_sets_used_at(self):
        invitation = self._make_invitation()
        now = timezone.now()

        invitation.mark_used(at=now)
        invitation.refresh_from_db()

        self.assertEqual(invitation.used_at, now)

    def test_mark_used_is_idempotent(self):
        invitation = self._make_invitation()
        first = timezone.now()
        second = first + timedelta(minutes=5)

        invitation.mark_used(at=first)
        invitation.mark_used(at=second)
        invitation.refresh_from_db()

        self.assertEqual(invitation.used_at, first)

    def test_mark_send_succeeded_sets_status_and_timestamps(self):
        invitation = self._make_invitation()
        now = timezone.now()

        invitation.mark_send_succeeded(at=now)
        invitation.refresh_from_db()

        self.assertEqual(invitation.send_status, SendStatus.SENT)
        self.assertEqual(invitation.last_send_attempt_at, now)
        self.assertEqual(invitation.sent_at, now)

    def test_mark_send_failed_sets_failed_and_attempted_at_only(self):
        invitation = self._make_invitation()
        now = timezone.now()

        invitation.mark_send_failed(at=now)
        invitation.refresh_from_db()

        self.assertEqual(invitation.send_status, SendStatus.FAILED)
        self.assertEqual(invitation.last_send_attempt_at, now)
        self.assertIsNone(invitation.sent_at)

    def test_save_normalizes_email(self):
        invitation = self._make_invitation(email="  INVITED@EXAMPLE.COM  ")
        invitation.refresh_from_db()

        self.assertEqual(invitation.email, "invited@example.com")
