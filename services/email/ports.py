"""
メールを送信するオブジェクトはどのような構成になっているべきかを規定する抽象ストラテジー

- あくまで持つべきメソッドを規定
- メールの送信元や送信先などは、types.pyに任せる
"""
from typing import Protocol
from .types import MailMessage


class EmailSender(Protocol):
    """メール送信プロバイダが満たすべきインターフェース"""

    def send(self, message: MailMessage) -> None:
        """MailMessage を受け取り、メールを1通送信する"""
        ...