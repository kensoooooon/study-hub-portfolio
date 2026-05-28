"""
入力されたメールアドレスの正規化とは別に、メールアドレスとしての有効性を検証
"""
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from accounts.services.exceptions import InvalidEmailError


def validate_email_address(email: str | None) -> None:
    """メールアドレスの形式が有効なものかを確認し、判定する

    Args:
        email (str | None): 検証したいメールアドレス

    Raises:
        InvalidEmailError: メールアドレスとして認められない形式のときに送出される
    """
    if not email:
        raise InvalidEmailError("不正なメールアドレスです。")

    try:
        validate_email(email)
    except ValidationError as e:
        raise InvalidEmailError("不正なメールアドレスです。") from e