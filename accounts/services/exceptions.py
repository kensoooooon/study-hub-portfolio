"""
想定されるエラーと想定外のエラーを区別するための独自エラー群

InvitationErrorを継承したエラー群については、
    raise InvitationEmailSendError()にすればuser_messageを、
    raise InvitationEmailSendError("hoge...")とすればそのメッセージを優先して出力する
"""


class InvitationError(Exception):
    """招待関連のベース例外"""
    user_message = "招待処理に失敗しました。"

    def __init__(self, message: str | None = None):
        super().__init__(message or self.user_message)


class InvitationEmailSendError(InvitationError):
    """メール送信失敗"""
    user_message = "招待メールの送信に失敗しました。"


class InvitationRecipientRefusedError(InvitationEmailSendError):
    """宛先がSMTPレベルで拒否された"""
    user_message = "メールアドレスが誤っている、または受信側で受け付けられませんでした。"


class InvitationEmailAuthError(InvitationEmailSendError):
    """SMTP認証失敗"""
    user_message = "メール送信設定に問題があります。"


class InvitationEmailConnectionError(InvitationEmailSendError):
    """SMTP接続失敗"""
    user_message = "メールサーバーへの接続に失敗しました。"


class InvitationEmailTimeoutError(InvitationEmailSendError):
    """SMTPタイムアウト"""
    user_message = "メール送信がタイムアウトしました。"


class InvitationEmailUnexpectedError(InvitationEmailSendError):
    """想定外のメール送信失敗"""
    user_message = "招待メール送信中に予期しないエラーが発生しました。"


class InvalidEmailError(InvitationError):
    """不正なメール"""
    user_message = "不正なメールアドレスです。"


class InvitationAlreadyExistsError(InvitationError):
    """既存招待が存在"""
    user_message = "すでに有効な招待が存在しています。"


class InvitationPermissionDeniedError(InvitationError):  # これはservicesではなくviews層で利用?
    """招待する権限が存在しない"""
    user_message = "招待する権限がありません。"


class InvitationOrganizationNotFoundError(InvitationError):
    """招待対象の組織が存在しない"""
    user_message = "招待対象の組織が存在しません。"


class InvalidTokenError(InvitationError):
    """トークンが無効"""
    user_message = "無効な招待リンクです。"


class InvitationDoesNotExist(InvitationError):
    """招待が存在しない"""
    user_message = "招待が存在しません。"


class InactiveInvitationError(InvitationError):
    """呼び出そうとした招待が無効である"""
    user_message = "この招待はすでに無効です。"


class ExistingUserError(InvitationError):
    """招待の対象ユーザーが既に存在している"""
    user_message = "対象ユーザーはすでに存在しています。"


class OrganizationAdministratorAlreadyAssignedError(InvitationError):
    """対象ユーザーは既にこの組織の組織管理者である"""
    user_message = "すでに当該組織の組織管理者です。"


class ExistingUserWrongRoleError(InvitationError):
    """対象ユーザーはその組織に存在するが、組織管理者ロールではない"""
    user_message = "すでに組織に別の役職として登録されています。"


class OrganizationAdministratorExistsInAnotherOrganizationError(InvitationError):
    """対象ユーザーは別組織の組織管理者として存在している"""
    user_message = "すでに他の組織で組織管理者として登録されています。"


class AnotherRoleExistsInAnotherOrganizationError(InvitationError):
    """対象ユーザーは別組織の組織管理者以外として存在している"""
    user_message = "すでに別組織において、異なる役職として登録されています。"


class UserStateError(Exception):
    """ユーザーデータの整合性異常"""
    pass


class InvalidUserRoleError(UserStateError):
    """ユーザーに想定外のroleが設定されている"""
    pass


class MissingRoleObjectError(UserStateError):
    """ユーザーに対応する役職オブジェクトが存在しない"""
    pass


class MissingBelongedOrganizationError(UserStateError):
    """ユーザーの所属組織が存在しない"""
    pass