"""
GmailSMTPを利用するための具象ストラテジー

- EmailSenderを明示的に継承することで、送信オブジェクトの規程が明確に
- DjangoのEmailMessageを活用することで、形式を統一し、テスト等が容易に
"""
from django.core.mail import EmailMessage
from services.email.ports import EmailSender
from services.email.types import MailMessage


class GmailSMTPSender(EmailSender):
    def send(self, message: MailMessage) -> None:

        email = EmailMessage(
            subject=message.subject,
            body=message.body,
            from_email=message.from_email,
            to=list(message.to),
            reply_to=list(message.reply_to) if message.reply_to else None,
        )

        email.send()
