"""
メールのリンクがクリックされて、トークンを受信(ここまでviews)した後の処理を行う
"""
import logging
from typing import NamedTuple


from django.core import signing
from django.db import transaction

from accounts.services.invitation_tokens import SALT, EXPIRE_DAYS
from accounts.services.exceptions import InvalidTokenError, InvitationDoesNotExist, InactiveInvitationError, ExistingUserError
from accounts.services.normalize_email import normalize_email
from accounts.models import Invitation, InvitationRole, OrganizationAdministrator, BaseUser, Organization


logger = logging.getLogger(__name__)


EXPIRE_SECONDS = 86400 * EXPIRE_DAYS


def load_invitation_id_from_token(*, token: str) -> int:
    """トークンから招待IDを取得する

    Args:
        token (str): views.pyから渡されたトークン

    Returns:
        invitation_id (int): トークンから取得した招待ID
    """
    # トークンの有効性チェック
    try:
        data = signing.loads(token, salt=SALT, max_age=EXPIRE_SECONDS)
    except signing.BadSignature as e:
        logger.warning("トークンの署名が不正です。")
        raise InvalidTokenError("不正なトークンです。") from e
    except signing.SignatureExpired as e:
        logger.warning("トークンの期限が切れています。")
        raise InvalidTokenError("不正なトークンです。") from e
    
    # 値が存在するか否か
    if not isinstance(data, dict):
        logger.warning("トークンの形式が不正です。")
        raise InvalidTokenError("不正なトークンです。")
    if "invitation_id" not in data:
        logger.warning("トークンに招待IDが含まれていません。")
        raise InvalidTokenError("不正なトークンです。")
    raw_invitation_id = data["invitation_id"]
    
    # 整数として解釈できるか？ 
    try:
        invitation_id = int(raw_invitation_id)
    except (TypeError, ValueError) as e:
        logger.warning("招待IDが整数として解釈できません。")
        raise InvalidTokenError("不正なトークンです。") from e

    if invitation_id <= 0:
        logger.warning("招待IDが不正な値です。")
        raise InvalidTokenError("不正なトークンです。")

    return invitation_id


def get_acceptable_invitation_by_id(*, invitation_id: int) -> Invitation:
    """IDから受理可能な招待を取得

    Args:
        invitation_id (int): 取得したい招待ID

    Returns:
        Invitation: 受理可能な招待
    """
    try:
        invitation = Invitation.objects.select_related("organization").get(id=invitation_id)
    except Invitation.DoesNotExist:
        ctx = {"invitation_id": invitation_id}
        logger.warning(
            "招待が存在しません。",
            extra=ctx
        )
        raise InvitationDoesNotExist("無効な招待です。")
    
    if not invitation.is_active:
        ctx = {"invitation_id": invitation_id}
        logger.warning(
            "有効な招待ではありません。",
            extra=ctx
        )
        raise InactiveInvitationError("無効な招待です。")
    
    return invitation


def get_acceptable_invitation_by_token(*, token: str) -> Invitation:
    """トークンから有効な招待を取得するヘルパー関数
    
    Args:
        token (str): リクエストにパラメータとして飛んでくるトークン
    
    Returns:
        invitation (Invitation): 有効な招待
    """
    invitation_id = load_invitation_id_from_token(token=token)
    invitation = get_acceptable_invitation_by_id(invitation_id=invitation_id)
    return invitation


class AcceptInvitationDisplayInfo(NamedTuple):
    """招待されたユーザーの入力画面に必要な情報を規定

    Attributes:
        organization_name (str): 組織名
        email (str): メールアドレス
        role (str): 招待された役職
    """
    organization_name: str
    email: str
    role: str


def build_accept_invitation_display_info(*, token: str) -> AcceptInvitationDisplayInfo:
    """組織管理者登録画面に必要な情報の構築

    Args:
        token (str): 外部から入力されたトークン

    Returns:
        (AcceptInvitationDisplayInfo): 画面表示の構築に必要になる情報群 
    """
    invitation = get_acceptable_invitation_by_token(token=token)
    return AcceptInvitationDisplayInfo(
        organization_name=invitation.organization.name,
        email=invitation.email,
        role=invitation.role,
    )

def create_org_admin(*, username: str, email: str, password: str, organization: Organization) -> OrganizationAdministrator:
    user = OrganizationAdministrator(
        username=username,
        email=email,
        role=InvitationRole.ORG_ADMIN,
    )
    user.set_password(password)
    user.save()
    user.organizations.add(organization)
    return user


def check_and_confirm_invitation(*, token: str, username: str, password: str) -> BaseUser:
    """入力された情報から招待を確定させる関数
    
    Args:
        token (str): リンクから引き継いだtoken(input type:hidden想定)
        username (str): ユーザーが入力した名前(forms.pyで事前検証すること!)
        password (str): ユーザーが入力したパスワード
    
    Returns:
        user (BaserUser): 作成したユーザー
    
    Notes:
        外部入力が絡むので、あえてintegrityerrorで握らない構成
    """
    invitation = get_acceptable_invitation_by_token(token=token)  # いきなり登録するのではなく、再度有効化どうかをチェックしつつ呼び出し
    invitation_id = invitation.id
    with transaction.atomic():
        invitation = get_invitation_for_acceptance_lock(invitation_id=invitation_id)
        if not invitation.is_active:  # 再度アクティブかを確認
            ctx = {"invitation_id": invitation_id}
            logger.warning(
                "ロック取得後、招待が既に無効になっています。",
                extra=ctx
            )
            raise InactiveInvitationError("無効な招待です。")
        
        email = invitation.email
        normalized_email = normalize_email(email)
        if BaseUser.objects.filter(email=normalized_email).exists():  # ユーザーが既に存在している場合
            ctx = {"invitation_id": invitation_id}
            logger.warning(
                "メールアドレスが衝突しました。既存ユーザーです。",
                extra=ctx
            )
            raise ExistingUserError("このメールアドレスはすでに利用されています。")
        role = invitation.role
        if role == InvitationRole.ORG_ADMIN:  # 組織管理者のみ対応
            org = invitation.organization
            user = create_org_admin(
                username=username,
                email=normalized_email,
                password=password,
                organization=org
            )
        else:
            ctx = {
                "invitation_id": invitation_id,
                "role": role,
                }
            logger.warning(
                "未設定のロール作成が要求されました。",
                extra=ctx
            )
            raise InactiveInvitationError("無効な招待です。")
        invitation.mark_used()
        return user



def get_invitation_for_acceptance_lock(*, invitation_id: int) -> Invitation:
    """トランザクション内で呼ぶための専用関数

    Args:
        invitation_id (int): 呼び出したい招待ID

    Returns:
        Invitation: 適用したい招待
    """
    return Invitation.objects.select_related("organization").select_for_update().get(id=invitation_id)