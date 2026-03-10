from typing import Optional
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

from accounts.models import BaseUser
from math_trainer.models import ProblemSession

import logging

logger = logging.getLogger(__name__)


def session_access_check(user: BaseUser, raw_session_id: Optional[str], *, mode: Optional[str] = None,) -> ProblemSession:
    """
    与えられたユーザー情報とセッションIDから、アクセス権をチェックした ProblemSession を返す。

    Args:
        user (BaseUser): 対象となるユーザー
        raw_session_id (str | None): セッションID（UUID文字列想定）
        mode (str | None): printタイプかdisplayタイプかの指定(任意)

    Returns:
        ProblemSession: アクセスが許可された ProblemSession

    Raises:
        PermissionDenied: 不正なセッションIDまたはアクセス権なしの場合
    """
    if not raw_session_id:
        logger.warning(
            "セッションIDが指定されていません。(user.id: %s, raw_session_id: %s)",
            getattr(user, "id", None), raw_session_id,
        )
        raise PermissionDenied("不正なアクセスです。")

    qs = ProblemSession.objects.all()
    if mode:
        qs = qs.filter(mode=mode)
    problem_session = get_object_or_404(qs, pk=raw_session_id)

    if problem_session.can_be_accessed_by(user):
        return problem_session

    logger.warning(
        "アクセス権のないユーザーによるProblemSessionへのアクセスが発生しました。(user.id: %s, problem_session.id: %s)",
        getattr(user, "id", None), problem_session.id
    )
    raise PermissionDenied("不正なアクセスです。")
