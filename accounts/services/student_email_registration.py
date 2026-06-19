"""
LINE経由の生徒メールアドレス登録に関するサービス層。

責務:
    - メール登録コマンド判定
    - 登録トークン発行（古いトークンのrevoke + 新規発行をatomicに実行）
    - トークン取得・検証
    - メールアドレス登録確定（transaction.atomic + select_for_update）
    - LINEイベント用応答文面の生成
"""

import hashlib
import logging
import secrets
from datetime import timedelta

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import (
    BaseUser,
    StudentEmailRegistrationToken,
    Student,
    Organization
)
from accounts.services.exceptions import (
    StudentEmailAlreadyRegisteredError,
    StudentEmailConflictError,
    StudentEmailRegistrationTokenInactiveError,
    StudentEmailRegistrationTokenInvalidError,
)
from accounts.services.normalize_email import normalize_email

logger = logging.getLogger(__name__)

EMAIL_REGISTRATION_TOKEN_EXPIRE_MINUTES = 15


def _hash_raw_token(raw_token: str) -> str:
    """
    トークンをhash化
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()


def is_email_registration_command(message_text: str) -> bool:
    """「メール登録」または「メールアドレス登録」と一致するか判定する。"""
    return message_text.strip() in ("メール登録", "メールアドレス登録")


def issue_email_registration_token(
    *,
    student: Student,
    organization: Organization,
    line_user_id: str
    ) -> str:
    """トークンをDBに登録し、raw_tokenを発行する

    Args:
        student (Student): トークンに紐づけたい生徒
        organization (Organization): 生徒を紐づける組織
        line_user_id (str): 生徒に紐づいたLINEユーザーID

    Returns:
        raw_token (str): リンクのパラメータとして付加されるトークン
    
    Notes:
        有効期限はトップレベルの定数により決定する
    """
    now = timezone.now()
    expires_at = now + timedelta(minutes=EMAIL_REGISTRATION_TOKEN_EXPIRE_MINUTES)

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_raw_token(raw_token)

    with transaction.atomic():
        existing_tokens = (
            StudentEmailRegistrationToken.objects
            .select_for_update()
            .filter(
                student=student,
                used_at__isnull=True,
                revoked_at__isnull=True,
            )
        )
        for token in existing_tokens:
            token.revoke(at=now)

        StudentEmailRegistrationToken.objects.create(
            student=student,
            organization=organization,
            line_user_id=line_user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

    return raw_token


def get_token_by_raw(raw_token: str) -> StudentEmailRegistrationToken:
    """与えられたraw_tokenをハッシュ化し、それに対応したトークンオブジェクトを返す

    Args:
        raw_token (str): 取得したいトークンに紐づくraw_token

    Raises:
        StudentEmailRegistrationTokenInvalidError: トークンが不正、ここでは存在しない場合に送出

    Returns:
        StudentEmailRegistrationToken: raw_tokenに紐づくトークン
    """
    token_hash = _hash_raw_token(raw_token)
    try:
        return (
            StudentEmailRegistrationToken.objects
            .select_related("student", "organization")
            .get(token_hash=token_hash)
        )
    except StudentEmailRegistrationToken.DoesNotExist:
        raise StudentEmailRegistrationTokenInvalidError()


def confirm_email_registration(*, raw_token: str, email: str) -> None:
    """メールアドレスの最終登録を確定させる

    Args:
        raw_token (str): 検証用の入力されるトークン
        email (str): 登録したいアドレス

    Raises:
        StudentEmailRegistrationTokenInvalidError: raw_tokenに対応するトークンが存在しない
        StudentEmailRegistrationTokenInactiveError: トークンは非アクティブで利用できない
        StudentEmailRegistrationTokenInactiveError: 対応する生徒が非アクティブ
        StudentEmailRegistrationTokenInactiveError: 発行時と登録時で組織が異なる
        StudentEmailRegistrationTokenInactiveError: 発行時と登録時でLINEIDが異なる
        StudentEmailAlreadyRegisteredError: メールアドレス登録済み(最終防御として)
        StudentEmailConflictError: 入力されたメールアドレスが既存ユーザーで使用されている    
    
    Notes:
        メールアドレスの衝突は全ユーザー単位で見られている点に注意
    """
    token_hash = _hash_raw_token(raw_token)

    with transaction.atomic():
        try:
            token = (
                StudentEmailRegistrationToken.objects
                .select_for_update()  # 他リクエストからのアクセスをロック
                .select_related("student", "organization")
                .get(token_hash=token_hash)
            )
        except StudentEmailRegistrationToken.DoesNotExist:
            raise StudentEmailRegistrationTokenInvalidError()

        if not token.is_active:
            raise StudentEmailRegistrationTokenInactiveError()

        student = token.student

        if not student.is_active:
            # 対象の生徒が非アクティブの場合は、トークン自体も非アクティブと扱う
            # 将来的に細かい条件がでてきたら、例外名の変更・新設を検討
            raise StudentEmailRegistrationTokenInactiveError()

        # token 発行時の organization / line_user_id と現在の student 側の値が一致することを確認
        if token.organization_id != student.organization_id:
            raise StudentEmailRegistrationTokenInactiveError()

        if token.line_user_id != student.line_user_id:
            raise StudentEmailRegistrationTokenInactiveError()

        if student.email:
            raise StudentEmailAlreadyRegisteredError()

        normalized = normalize_email(email)

        if BaseUser.objects.filter(email=normalized).exists():
            raise StudentEmailConflictError()

        student.email = normalized
        student.save(update_fields=["email"])

        # メール登録フローではパスワードを変更しない。
        # 通常は名前登録フローで初期パスワードが設定済みのため、
        # usable password がない場合はデータ整合性の異常として記録する。
        if not student.has_usable_password():
            logger.warning(
                "[email_registration] student has no usable password after email registration",
                extra={"student_id": student.pk},
            )

        token.mark_used()


def maybe_build_email_registration_response(
    *, request, student, line_channel, message_text: str
) -> str | None:
    """LINE メッセージがメール登録コマンドなら応答文面を返す。

    コマンドに該当しない場合は None を返す。
    student が inactive の場合は None を返す（webhook 側で弾かれているはずだが多重防御）。
    student.email が登録済みの場合は登録済みメッセージを返す。
    それ以外の場合はトークンを発行して登録 URL を含む文面を返す。

    Notes:
        - student が inactive の場合は None を返す(通常は webhook 側の共通ガードで先に弾かれるため、ここでは多重防御に留める）
        - organizationにおいても同様
    """
    if not is_email_registration_command(message_text):
        return None

    if not student.is_active:
        return None

    if student.organization_id != line_channel.organization_id:
        return None

    login_url = request.build_absolute_uri(reverse("accounts_auth:login"))

    if student.email:
        return (
            "すでにメールアドレスは登録済みです。\n"
            f"こちらからログインできます: {login_url}"
        )

    raw_token = issue_email_registration_token(
        student=student,
        organization=line_channel.organization,
        line_user_id=student.line_user_id,
    )

    reg_url = request.build_absolute_uri(
        reverse("user_register:register_email")
    ) + f"?t={raw_token}"

    return (
        "メールアドレスを登録してください。\n"
        "以下のリンクは15分間有効です。\n"
        f"{reg_url}\n\n"
        "登録後は、登録したメールアドレスでログインできます。\n"
        f"こちらがログイン先です: {login_url}"
    )
