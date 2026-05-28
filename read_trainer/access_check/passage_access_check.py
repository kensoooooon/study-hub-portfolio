"""
長文取得とアクセスチェックを兼ねる関数の配置先
"""
from typing import Optional
from django.shortcuts import get_object_or_404
from django.http import Http404

from read_trainer.access_check.student_access_check import ensure_can_access_student
from read_trainer.models import ReadingPassage
from accounts.models import BaseUser

import logging

logger = logging.getLogger(__name__)


def parse_passage_id_or_404(user: BaseUser, raw_passage_id: Optional[str]) -> int:
    """与えられた長文IDがきちんと自然数形式として解釈できるかをチェックする

    Args:
        user (BaseUser): 取得を試みているユーザー
        raw_passage_id (Optional[str]): 取得したい長文ID

    Raises:
        Http404: 整数として解釈できない場合
        Http404: 整数ではあるが、自然数でない場合

    Returns:
        int: 確認された長文ID
    """
    try:
        passage_id = int(raw_passage_id)
    except (ValueError, TypeError, AttributeError):
        logger.warning(
            "不正な形式のpassage_idが指定されました。(user.id=%s, raw_passage_id=%s)",
            getattr(user, "id", None),
            raw_passage_id,
        )
        raise Http404

    if passage_id <= 0:
        logger.warning(
            "不正な範囲のpassage_idが指定されました。(user.id=%s, passage_id=%s)",
            getattr(user, "id", None),
            passage_id,
        )
        raise Http404

    return passage_id


def passage_access_check(
        user: BaseUser,
        raw_passage_id: Optional[str],
        source_type: Optional[str] = None,
        expected_student_id: Optional[str] = None
        ) -> ReadingPassage:
    """指定のユーザーが与えられた長文に正当にアクセスできるかをチェックし、長文オブジェクトを返す

    Args:
        user (BaseUser): 取得を試みているユーザー
        raw_passage_id (OPtional[str]): 取得したい長文
        source_type (Optional[str]): 長文のタイプ(textbook or eiken)
        expected_student_id (Optional[str]): 想定される作成者の生徒ID

    Returns:
        (ReadingPassage): 正当であるかのチェックを突破した長文オブジェクト

    Raises:
        Http404: 作成者が紐付けられていないときは、安全側に倒してアクセス不可へ
        Http404: 想定されないタイプの長文が呼び出されたとき
        Http404: 想定される作成者と実際の作成者が一致しない場合
    """
    if not raw_passage_id:
        logger.warning(
            "passage_id が指定されていません。(user.id=%s)",
            getattr(user, "id", None),
        )
        raise Http404
    
    passage_id = parse_passage_id_or_404(user, raw_passage_id)

    if source_type is None:
        passage = get_object_or_404(
            ReadingPassage.objects.visible_to(user),
            pk=passage_id,
        )
    elif source_type in ["textbook", "eiken"]:
        passage = get_object_or_404(
            ReadingPassage.objects.visible_to(user),
            pk=passage_id,
            source_type=source_type
        )
    else:
        logger.warning(
            "想定していないタイプの長文が呼び出されようとしました。(user.id=%s, source_type=%s)",
            getattr(user, "id", None),
            source_type,
        )
        raise Http404

    student = passage.created_by
    if student is None:
        raise Http404
    if expected_student_id is not None:
        if str(student.id) != str(expected_student_id):
            logger.warning(
                "長文の作成者が想定される作成者と一致しません。(student_id: %s, expected: %s)",
                student.id,
                expected_student_id
            )
            raise Http404

    ensure_can_access_student(user, student)
    return passage
