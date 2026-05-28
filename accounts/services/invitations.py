"""
メール送信以外の招待フローチャートを担当するモジュール

招待可能か判定
Invitation 作成
期限設定
トークン生成
招待URL生成
invitation_mails.py 呼び出し
"""
# 時間経過(expires_at)
from datetime import timedelta
# 招待
from django.core import signing

import logging
from datetime import datetime
from urllib.parse import urlencode


from django.utils import timezone
from django.db import transaction
from django.db import IntegrityError


from accounts.models import Invitation, BaseUser, InvitationRole, Organization
from accounts.selectors import visible_organizations_qs
from accounts.services.invitation_mails import invitation_send_mail
from accounts.services.exceptions import (
    InvitationAlreadyExistsError,
    InvitationOrganizationNotFoundError,
    InvalidEmailError,
    OrganizationAdministratorAlreadyAssignedError,
    ExistingUserWrongRoleError,
    OrganizationAdministratorExistsInAnotherOrganizationError,
    AnotherRoleExistsInAnotherOrganizationError,
    InvalidUserRoleError,
    MissingRoleObjectError,
    MissingBelongedOrganizationError,
    InvitationEmailSendError,
)
from accounts.services.normalize_email import normalize_email
from accounts.services.validate_email import validate_email_address
from accounts.services.invitation_tokens import SALT, EXPIRE_DAYS

logger = logging.getLogger(__name__)


def _revoke_expired_invitations(*, organization: Organization, normalized_email_address: str, now: datetime) -> None:
    """期限切れの招待をまとめて無効化する

    Args:
        organization (Organization): チェック対象の組織
        normalized_email_address (str): 「正規化された」メールアドレス
        now (datetime): timezone.now()で取得した、処理が始まる起点となる時刻データ 
    """
    stale_invitations = Invitation.objects.filter(
        organization=organization,
        email=normalized_email_address,
        used_at__isnull=True,  # 利用されていない
        revoked_at__isnull=True,  # 無効化されていない
        expires_at__lt=now,  # 使用期限が切れている
    )

    for stale_invitation in stale_invitations:
        stale_invitation.revoke(at=now)


def _raise_if_active_invitation_exists(*, organization: Organization, normalized_email_address: str, now: datetime) -> None:
    """アクティブな招待が存在しているとエラーを送出してくれるチェック用の関数

    Args:
        organization (Organization): チェック対象の組織
        normalized_email_address (str): 「正規化された」メールアドレス
        now (datetime): timezone.now()で取得した、処理が始まる起点となる時刻データ 

    Raises:
        InvitationAlreadyExistsError: アクティブな招待が存在していると送出
    """
    active_exists = Invitation.objects.filter(
        organization=organization,
        email=normalized_email_address,
        used_at__isnull=True,
        revoked_at__isnull=True,
        expires_at__gte=now,
    ).exists()

    if active_exists:
        ctx = {
            "organization_id": organization.id,
            "normalized_email_address": normalized_email_address,
        }
        logger.warning(  # 正常な防止処理が動いている
            "すでに有効な招待が存在してます",
            extra=ctx
            )
        raise InvitationAlreadyExistsError()


def _check_invited_user_status(*, normalized_email_address:str, organization_id: int) -> None:
    """アドレスに紐づくユーザーが本当に新規組織管理者として招待すべき相手かを判定

    Args:
        normalized_email_address (str): 正規化されたアドレス
        organization_id (int): チェックしたい組織
    
    Note:
        自組織or他組織×組織管理者or別ロールで合計4通り
    """
    def _get_role_object_or_raise(user: BaseUser):
        role_object = user.get_role_object()
        if role_object is None:
            logger.error(
                "ユーザーに対応するロールオブジェクトが存在しません。",
                extra={
                    "user_id": user.id,
                    "role": user.role,
                    "normalized_email_address": normalized_email_address,
                    "organization_id": organization_id},
            )
            raise MissingRoleObjectError("不正なユーザーです。")
        return role_object

    user = BaseUser.objects.filter(email=normalized_email_address).first()  # クエリセット→firstで回数を抑える工夫
    if user is None:
        return
    if user.role == "organization_administrator":  # 組織管理者である
        role_object = _get_role_object_or_raise(user)
        if role_object.organizations.filter(id=organization_id).exists():  # すでにその組織に割り当てられている
            raise OrganizationAdministratorAlreadyAssignedError()
        raise OrganizationAdministratorExistsInAnotherOrganizationError()  # 別の組織に割り当てられている
    elif (user.role == "student") or (user.role == "teacher") or (user.role == "classroom_administrator"):  # 生徒、講師、教室管理者は単体
        role_object = _get_role_object_or_raise(user)
        belonged_organization = role_object.organization
        if belonged_organization is None:
            logger.error(
                "ユーザーの所属組織が設定されていません。",
                extra={"user_id": user.id, "role": user.role},
            )
            raise MissingBelongedOrganizationError("不正なユーザーです。")
        if belonged_organization.id == organization_id:  # 同じ組織に別ロールとして所属していることが確定
            raise ExistingUserWrongRoleError()
        else:  # 他の組織で別の役職をやっている
            raise AnotherRoleExistsInAnotherOrganizationError()
    else:
        logger.error(
            "想定外のロールが設定されています。",
            extra={"user_id": user.id, "role": user.role}
        )
        raise InvalidUserRoleError("不正なユーザーです。")


def invite_organization_administrator(*, accept_base_url: str, user: BaseUser, organization_id: int, email_address: str) -> None:
    """招待に関連するメール送信以外の処理を担当(DB保存など)

    Args:
        accept_base_url (str): 招待に際して利用するURLのベース
        user (BaseUser): 招待者
        organization_id (int): 管理者に指定したい組織
        email_address (str): 組織管理者になる予定の人のメールアドレス

    Raises:
        InvitationOrganizationNotFoundError: そもそも管理先の対象組織が存在しないとき
        InvitationAlreadyExistsError: 以前送った有効な招待がまだ残っているとき

    Note:
        from django.conf import settings
        from django.urls import reverse

        accept_path = reverse("accounts:accept_org_admin_invitation")
        accept_url_base = f"{settings.APP_PUBLIC_BASE_URL}{accept_path}"みたいな感じで、viewsからベースが飛んでくる
        飛んできたベースにトークンを追加し、さらにメールにわたす感じ
    """
    # 可視範囲の組織のみを表示し、可視範囲外の組織は存在しないものとして扱う
    org_candidates = visible_organizations_qs(user)
    organization = org_candidates.filter(id=organization_id).first()
    if organization is None:
        raise InvitationOrganizationNotFoundError("招待対象の組織が存在しません。")
    normalized_email_address = normalize_email(email_address)
    if not(normalized_email_address):
        ctx = {
            "user": user.username,
            "organization_id": organization.id,
            "email_address": email_address,
            "normalized_email_address": normalized_email_address
        }
        logger.warning(
            "不正なメールアドレスが入力されました。",
            extra=ctx
        )
        raise InvalidEmailError("不正なメールアドレスです。")
    validate_email_address(normalized_email_address)
    
    # メール正規化後のここで、4パターンのいずれか([自組織, 他組織]×[組織管理者, 別ロール])のチェックを実施
    _check_invited_user_status(normalized_email_address=normalized_email_address, organization_id=organization_id)

    with transaction.atomic():
        now = timezone.now()
        
        # # 期限切れなのに未 revoke のまま残っている招待を整理
        _revoke_expired_invitations(organization=organization, normalized_email_address=normalized_email_address, now=now)
        # アクティブなものが残っていたら招待中止
        _raise_if_active_invitation_exists(organization=organization, normalized_email_address=normalized_email_address, now=now)

        # 同時にアクセスが走った時用
        try:
            invitation = Invitation.objects.create(
                organization=organization,
                email=normalized_email_address,
                role=InvitationRole.ORG_ADMIN,
                expires_at=now + timedelta(days=EXPIRE_DAYS),
                invited_by=user,
            )
        except IntegrityError as e:
            logger.warning(
                "招待作成時に一意制約へ衝突しました。",
                extra={
                    "organization_id": organization.id,
                    "normalized_email_address": normalized_email_address,
                    "invited_by": user.username,
                },
            )
            raise InvitationAlreadyExistsError(
                "すでに有効な招待が存在しています。"
            ) from e

        invitation_id = invitation.id
        payload = {"invitation_id": invitation_id}
        token = signing.dumps(payload, salt=SALT, compress=True)
        # invite_url = accept_base_url + f"?t={token}"
        parameters = {"t": token}
        invite_url = f"{accept_base_url}?{urlencode(parameters)}"
        def call_invitation_send_mail():
            invitation = None
            try:
                invitation = Invitation.objects.get(id=invitation_id)
                inviter_name = invitation.invited_by.username
                invitee_email = invitation.email
                invitation_send_mail(
                    inviter_name=inviter_name,
                    invitee_email=invitee_email,
                    invite_url=invite_url
                )
            except InvitationEmailSendError as e:  # メール送信フローの全体的な失敗
                ctx = {
                    "user": user.username,
                    "organization_id": organization.id,
                    "email_address": email_address,
                    "normalized_email_address": normalized_email_address,
                    "invitation_id": invitation_id,
                    "error_type": e.__class__.__name__,
                }
                logger.exception(
                    "招待メール送信に失敗しました。",
                    extra=ctx
                )
                if invitation is not None:
                    invitation.mark_send_failed()
            except Exception:  # メール送信中の想定していない例外
                ctx = {
                    "user": user.username,
                    "organization_id": organization.id,
                    "email_address": email_address,
                    "normalized_email_address": normalized_email_address,
                    "invitation_id": invitation_id,
                }
                logger.exception(
                    "招待メール送信処理中に予期しないエラーが発生しました。",
                    extra=ctx
                )
                if invitation is not None:
                    invitation.mark_send_failed()
            else:
                if invitation is not None:
                    invitation.mark_send_succeeded()

        transaction.on_commit(call_invitation_send_mail)        
