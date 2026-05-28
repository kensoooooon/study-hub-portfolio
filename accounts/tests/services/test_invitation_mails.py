from unittest.mock import Mock, patch
import smtplib


from django.test import SimpleTestCase, override_settings


from accounts.services.exceptions import InvitationEmailSendError
from accounts.services.invitation_mails import invitation_send_mail
from accounts.services.exceptions import (
    InvitationEmailAuthError,
    InvitationEmailConnectionError,
    InvitationEmailTimeoutError,
    InvitationEmailUnexpectedError,
    InvitationRecipientRefusedError,
)


@override_settings(
    DEFAULT_SUPPORT_EMAIL_ADDRESS="support@example.com",
    DEFAULT_FROM_EMAIL_ADDRESS="from@example.com",
    DEFAULT_REPLY_TO_EMAIL_ADDRESS="reply@example.com",
)
class InvitationSendMailTests(SimpleTestCase):
    def test_builds_mail_message_and_sends(self):
        fake_sender = Mock()

        with patch(
            "accounts.services.invitation_mails.decide_sender",
            return_value=fake_sender,
        ):
            invitation_send_mail(
                inviter_name="管理者A",
                invitee_email="  INVITED@EXAMPLE.COM  ",
                invite_url="https://example.com/accept?t=abc",
            )

        fake_sender.send.assert_called_once()
        mail_message = fake_sender.send.call_args.args[0]

        self.assertEqual(
            mail_message.subject,
            "管理者Aさんから組織管理者として招待されました",
        )
        self.assertEqual(mail_message.to, ["invited@example.com"])
        self.assertEqual(mail_message.from_email, "from@example.com")
        self.assertEqual(mail_message.reply_to, ["reply@example.com"])
        self.assertIn("<support@example.com>", mail_message.body)
        self.assertIn("https://example.com/accept?t=abc", mail_message.body)

    def test_maps_smtp_recipients_refused_to_recipient_refused_error(self):
        fake_sender = Mock()
        fake_sender.send.side_effect = smtplib.SMTPRecipientsRefused(
            recipients={"invited@example.com": (550, b"rejected")}
        )

        with patch(
            "accounts.services.invitation_mails.decide_sender",
            return_value=fake_sender,
        ):
            with self.assertRaises(InvitationRecipientRefusedError):
                invitation_send_mail(
                    inviter_name="管理者A",
                    invitee_email="invited@example.com",
                    invite_url="https://example.com/accept?t=abc",
                )

    def test_maps_smtp_authentication_error_to_auth_error(self):
        fake_sender = Mock()
        fake_sender.send.side_effect = smtplib.SMTPAuthenticationError(
            535, b"auth failed"
        )

        with patch(
            "accounts.services.invitation_mails.decide_sender",
            return_value=fake_sender,
        ):
            with self.assertRaises(InvitationEmailAuthError):
                invitation_send_mail(
                    inviter_name="管理者A",
                    invitee_email="invited@example.com",
                    invite_url="https://example.com/accept?t=abc",
                )

    def test_maps_smtp_connect_error_to_connection_error(self):
        fake_sender = Mock()
        fake_sender.send.side_effect = smtplib.SMTPConnectError(
            421, "connect failed"
        )

        with patch(
            "accounts.services.invitation_mails.decide_sender",
            return_value=fake_sender,
        ):
            with self.assertRaises(InvitationEmailConnectionError):
                invitation_send_mail(
                    inviter_name="管理者A",
                    invitee_email="invited@example.com",
                    invite_url="https://example.com/accept?t=abc",
                )

    def test_maps_smtp_server_disconnected_to_connection_error(self):
        fake_sender = Mock()
        fake_sender.send.side_effect = smtplib.SMTPServerDisconnected(
            "server disconnected"
        )

        with patch(
            "accounts.services.invitation_mails.decide_sender",
            return_value=fake_sender,
        ):
            with self.assertRaises(InvitationEmailConnectionError):
                invitation_send_mail(
                    inviter_name="管理者A",
                    invitee_email="invited@example.com",
                    invite_url="https://example.com/accept?t=abc",
                )

    def test_maps_timeout_error_to_timeout_error(self):
        fake_sender = Mock()
        fake_sender.send.side_effect = TimeoutError("timeout")

        with patch(
            "accounts.services.invitation_mails.decide_sender",
            return_value=fake_sender,
        ):
            with self.assertRaises(InvitationEmailTimeoutError):
                invitation_send_mail(
                    inviter_name="管理者A",
                    invitee_email="invited@example.com",
                    invite_url="https://example.com/accept?t=abc",
                )

    def test_maps_unexpected_error_to_unexpected_error(self):
        fake_sender = Mock()
        fake_sender.send.side_effect = ValueError("unexpected")

        with patch(
            "accounts.services.invitation_mails.decide_sender",
            return_value=fake_sender,
        ):
            with self.assertRaises(InvitationEmailUnexpectedError):
                invitation_send_mail(
                    inviter_name="管理者A",
                    invitee_email="invited@example.com",
                    invite_url="https://example.com/accept?t=abc",
                )
