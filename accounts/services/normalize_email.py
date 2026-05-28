"""
Eメールの正規化を担当

- 保存時の正規化はBaseUserManagerが最低限保証している
- 検索時は怪しい
- とにかくメールアドレスを扱うときには噛ませるイメージで
"""

def normalize_email(email: str | None ) -> str | None:
    """メールアドレスをすべて小文字にする正規化を実施するための関数

    Args:
        email (str | None): 対象となるメールアドレス

    Returns:
        str | None: 正規化されたメールアドレス
    """
    if email is None:
        return None
    
    if not isinstance(email, str):
        return None
    
    stripped_email = email.strip()
    if stripped_email == "":
        return ""
    
    return stripped_email.lower()
