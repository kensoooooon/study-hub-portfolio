from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

from accounts.models import (
    BaseUser,
    Invitation,
    Organization,
    OrganizationAdministrator,
    Teacher,
    Student,
    ClassroomAdministrator
)
from accounts.services.exceptions import (
    AnotherRoleExistsInAnotherOrganizationError,
    ExistingUserWrongRoleError,
    InvalidEmailError,
    InvalidUserRoleError,
    InvitationAlreadyExistsError,
    InvitationOrganizationNotFoundError,
    MissingBelongedOrganizationError,
    MissingRoleObjectError,
    OrganizationAdministratorAlreadyAssignedError,
    OrganizationAdministratorExistsInAnotherOrganizationError,
)
from accounts.services.invitations import invite_organization_administrator

from accounts.models import SendStatus
from accounts.services.exceptions import InvitationEmailSendError


class InviteOrganizationAdministratorTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Org1")
        self.other_organization = Organization.objects.create(name="Org2")

        self.user = OrganizationAdministrator.objects.create_user(
            email="admin@example.com",
            password="testpass123",
            username="admin",
        )
        self.user.organizations.add(self.organization)

        # service側でも visible_organizations_qs(user) が通る必要がある
        view_permission = Permission.objects.get(codename="view_organization")
        self.user.user_permissions.add(view_permission)

        self.accept_base_url = "https://example.com/accept"

    @patch("accounts.services.invitations.invitation_send_mail")
    def test_success_creates_invitation(self, mock_send_mail):
        with self.captureOnCommitCallbacks(execute=True):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=self.organization.id,
                email_address="new@example.com",
            )

        self.assertEqual(Invitation.objects.count(), 1)
        invitation = Invitation.objects.get()
        self.assertEqual(invitation.organization, self.organization)
        self.assertEqual(invitation.email, "new@example.com")
        self.assertEqual(mock_send_mail.call_count, 1)

    def test_raises_when_invalid_email(self):
        with self.assertRaises(InvalidEmailError):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=self.organization.id,
                email_address="invalid-email",
            )

    def test_raises_when_organization_not_found(self):
        with self.assertRaises(InvitationOrganizationNotFoundError):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=9999,
                email_address="test@example.com",
            )

    def test_raises_when_existing_invitation(self):
        Invitation.objects.create(
            organization=self.organization,
            email="dup@example.com",
            role="organization_administrator",
            invited_by=self.user,
            expires_at=timezone.now() + timedelta(days=1),
        )

        with self.assertRaises(InvitationAlreadyExistsError):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=self.organization.id,
                email_address="dup@example.com",
            )

    def test_raises_when_existing_org_admin_same_org(self):
        existing = OrganizationAdministrator.objects.create_user(
            email="exist@example.com",
            password="testpass",
            username="exist",
        )
        existing.organizations.add(self.organization)

        with self.assertRaises(OrganizationAdministratorAlreadyAssignedError):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=self.organization.id,
                email_address="exist@example.com",
            )

    def test_raises_when_existing_org_admin_other_org(self):
        existing = OrganizationAdministrator.objects.create_user(
            email="exist@example.com",
            password="testpass",
            username="exist",
        )
        existing.organizations.add(self.other_organization)

        with self.assertRaises(OrganizationAdministratorExistsInAnotherOrganizationError):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=self.organization.id,
                email_address="exist@example.com",
            )

    def test_raises_when_teacher_same_org(self):
        teacher = Teacher(
            email="teacher@example.com",
            username="t1",
            organization=self.organization,
        )
        teacher.set_password("testpass")
        teacher.save()

        with self.assertRaises(ExistingUserWrongRoleError):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=self.organization.id,
                email_address="teacher@example.com",
            )

    def test_raises_when_teacher_other_org(self):
        teacher = Teacher(
            email="teacher@example.com",
            username="t1",
            organization=self.other_organization,
        )
        teacher.set_password("testpass")
        teacher.save()

        with self.assertRaises(AnotherRoleExistsInAnotherOrganizationError):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=self.organization.id,
                email_address="teacher@example.com",
            )

    def test_raises_when_role_object_missing(self):
        BaseUser.objects.create_user(
            email="broken@example.com",
            password="testpass",
            username="broken",
            role="teacher",
        )

        with self.assertRaises(MissingRoleObjectError):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=self.organization.id,
                email_address="broken@example.com",
            )

    def test_raises_when_teacher_has_no_org(self):
        teacher = Teacher(
            email="no-org@example.com",
            username="no-org",
            organization=None,
        )
        teacher.set_password("testpass")
        teacher.save()

        with self.assertRaises(MissingBelongedOrganizationError):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=self.organization.id,
                email_address="no-org@example.com",
            )

    def test_raises_when_invalid_role(self):
        BaseUser.objects.create_user(
            email="invalid-role@example.com",
            password="testpass",
            username="invalid",
            role="unknown",
        )

        with self.assertRaises(InvalidUserRoleError):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=self.organization.id,
                email_address="invalid-role@example.com",
            )

    @patch(
        "accounts.services.invitations.invitation_send_mail",
        side_effect=InvitationEmailSendError("smtp failed"),
    )
    def test_mail_failure_marks_invitation_failed_but_keeps_record(self, mock_send_mail):
        with self.captureOnCommitCallbacks(execute=True):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=self.organization.id,
                email_address="failed@example.com",
            )

        self.assertEqual(Invitation.objects.count(), 1)

        invitation = Invitation.objects.get(email="failed@example.com")
        self.assertEqual(invitation.send_status, SendStatus.FAILED)
        self.assertIsNotNone(invitation.last_send_attempt_at)
        self.assertIsNone(invitation.sent_at)
        mock_send_mail.assert_called_once()

    @patch("accounts.services.invitations.invitation_send_mail")
    def test_reinvite_revokes_expired_invitation_and_creates_new_one(self, mock_send_mail):
        expired = Invitation.objects.create(
            organization=self.organization,
            email="reinvite@example.com",
            role="organization_administrator",
            invited_by=self.user,
            expires_at=timezone.now() - timedelta(days=1),
        )

        with self.captureOnCommitCallbacks(execute=True):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=self.organization.id,
                email_address="reinvite@example.com",
            )

        expired.refresh_from_db()
        self.assertIsNotNone(expired.revoked_at)

        invitations = Invitation.objects.filter(
            organization=self.organization,
            email="reinvite@example.com",
        ).order_by("created_at")

        self.assertEqual(invitations.count(), 2)

        new_invitation = invitations.last()
        self.assertNotEqual(new_invitation.id, expired.id)
        self.assertTrue(new_invitation.is_active)
        mock_send_mail.assert_called_once()


    def test_raises_when_classroom_administrator_same_org(self):
        classroom_admin = ClassroomAdministrator(
            email="classroom-admin@example.com",
            username="ca1",
            organization=self.organization,
        )
        classroom_admin.set_password("testpass")
        classroom_admin.save()

        with self.assertRaises(ExistingUserWrongRoleError):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=self.organization.id,
                email_address="classroom-admin@example.com",
            )

    def test_raises_when_classroom_administrator_other_org(self):
        classroom_admin = ClassroomAdministrator(
            email="classroom-admin@example.com",
            username="ca2",
            organization=self.other_organization,
        )
        classroom_admin.set_password("testpass")
        classroom_admin.save()

        with self.assertRaises(AnotherRoleExistsInAnotherOrganizationError):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=self.organization.id,
                email_address="classroom-admin@example.com",
            )

    def test_raises_when_student_same_org(self):
        student = Student(
            email="student@example.com",
            username="s1",
            organization=self.organization,
            line_user_id="line-student-001",
        )
        student.set_password("testpass")
        student.save()

        with self.assertRaises(ExistingUserWrongRoleError):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=self.organization.id,
                email_address="student@example.com",
            )

    def test_raises_when_student_other_org(self):
        student = Student(
            email="student@example.com",
            username="s2",
            organization=self.other_organization,
            line_user_id="line-student-002",
        )
        student.set_password("testpass")
        student.save()

        with self.assertRaises(AnotherRoleExistsInAnotherOrganizationError):
            invite_organization_administrator(
                accept_base_url=self.accept_base_url,
                user=self.user,
                organization_id=self.organization.id,
                email_address="student@example.com",
            )
