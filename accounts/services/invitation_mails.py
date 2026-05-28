"""
メール送信を担当

- 本文の作成
- services呼び出して、メールをsendする
- smtpの処理フローで発生する各種例外を独自例外で包んで送出する
"""
import smtplib


from django.conf import settings


from accounts.services.exceptions import (
    InvitationRecipientRefusedError,
    InvitationEmailAuthError,
    InvitationEmailConnectionError,
    InvitationEmailTimeoutError,
    InvitationEmailUnexpectedError
)
from services.email.factory import decide_sender
from services.email.types import MailMessage
from accounts.services.normalize_email import normalize_email


def invitation_send_mail(*, inviter_name: str, invitee_email: str, invite_url: str) -> None:
    """招待メールを実際に送信する

    Args:
        inviter_name (str): 招待者の名前
        invitee_email (str): 招待対象のメールアドレス
        invite_url (str): 招待の本文に使うURL

    Raises:
        InvitationEmailSendError: メールの送信に失敗した際に送出
    """
    subject = f"{inviter_name}さんから組織管理者として招待されました"
    body = "正しい招待である場合は以下のURLをクリックしてください。URLの有効期限は72時間です。 \n"  # 改行は動作する？
    body += f"覚えがない場合は、お手数ですが、<{settings.DEFAULT_SUPPORT_EMAIL_ADDRESS}>までご連絡いただけると幸いです。\n"
    body += invite_url
    to = normalize_email(invitee_email)
    from_email = settings.DEFAULT_FROM_EMAIL_ADDRESS
    reply_to = [settings.DEFAULT_REPLY_TO_EMAIL_ADDRESS]
    mail_message = MailMessage(
        subject=subject,
        body=body,
        to=[to],
        from_email=from_email,
        reply_to=reply_to
    )
    sender = decide_sender()
    try:
        sender.send(mail_message)
    except smtplib.SMTPRecipientsRefused as e:  # SMTPレベルの宛先からの拒否
        raise InvitationRecipientRefusedError() from e
    except smtplib.SMTPAuthenticationError as e:  # SMTPの認証失敗
        raise InvitationEmailAuthError() from e
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected) as e:  # 接続、またはメールサーバー側のエラー
        raise InvitationEmailConnectionError() from e
    except TimeoutError as e:  # シンプルなタイムアウト
        raise InvitationEmailTimeoutError() from e
    except Exception as e:  # 想定外のエラー
        raise InvitationEmailUnexpectedError() from e