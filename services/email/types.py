"""
メールとは何かを規定する

- 必要最低限の実装
- 後に拡張するとしたら、たとえばhtml_body, attachments
"""

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class MailMessage:
    """メールが含むべきデータを規定
    
    Attributes:
        subject (str): 件名
        body (str): 本文
        to (Sequence[str]): 送信先の一覧
        from_email (str): 送信元
        reply_to (Sequence[str]): 返信先の一覧
    """
    subject: str
    body: str
    to: Sequence[str]
    from_email: str
    reply_to: Sequence[str] | None = None
