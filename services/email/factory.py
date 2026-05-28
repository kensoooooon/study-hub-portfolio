"""
settings.pyで決められた戦略を具体的に採用する場所
"""
from django.conf import settings
import logging

from services.email.providers.gmail_smtp import GmailSMTPSender
from services.email.ports import EmailSender

logger = logging.getLogger(__name__)


def decide_sender() -> EmailSender:
    """settings を見て利用するメール送信プロバイダを決定する"""

    email_host = settings.EMAIL_HOST

    if email_host == "smtp.gmail.com":
        return GmailSMTPSender()

    logger.warning(
        "未知のメールホストが指定されました",
        extra={"EMAIL_HOST": email_host},
    )

    raise ValueError(f"Unsupported EMAIL_HOST: {email_host}")
