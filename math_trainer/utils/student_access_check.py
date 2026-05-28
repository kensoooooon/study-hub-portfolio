from typing import Optional
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.http import Http404

import logging

from accounts.models import Student, BaseUser

from math_trainer.utils.is_check import is_student, is_admin_or_teacher


logger = logging.getLogger(__name__)


def student_access_check(user: BaseUser, raw_student_id: Optional[str]) -> Student:
    """ユーザーの生徒へのアクセスが正当なものかを判定する

    Args:
        user (BaseUser): チェック対象となるユーザー
        raw_student_id (Optional[str]): リクエストやセッション経由で取得した生徒ID

    Returns:
        Student: アクセスしたい生徒

    Raises:
        共通: 
            PermissionDenied: 未認証ユーザーによるアクセス
            PermissionDenied: 対象の生徒IDが指定されていないアクセス
            PermissionDenied: 正規ユーザーであれば必ず持っているはずのget_role_objectが働かないとき
            PermissionDenied: role_objがNoneで返ってきた時
        管理者: 
            Http404: アクティブでない生徒にアクセスしようとしたとき
            PermissionDenied: 管理者が権限外の生徒にアクセス
        生徒: 
            PermissionDenied: role_objがきちんと生徒になっていない場合
            Http404: アクティブでない生徒にアクセスが入った場合
            PermissionDenied: 生徒が自身以外の生徒にアクセス
            PermissionDenied: 想定していないロールによるアクセス
    """
    # 1) userの前提（login_requiredがあるなら冗長だが、関数単体の堅牢性は上がる）
    if not getattr(user, "is_authenticated", False):
        logger.warning("未認証ユーザーによるstudent_access_check呼び出し")
        raise PermissionDenied("不正なアクセスです。")

    # 2) student_id が必須ならここで弾く
    if not raw_student_id:
        logger.warning("student_id が指定されていません。(user.id=%s)", getattr(user, "id", None))
        raise PermissionDenied("不正なアクセスです。")

    # 3) ロールオブジェクト
    try:
        role_obj = user.get_role_object()
    except Exception:
        logger.exception("get_role_object に失敗しました。(user.id=%s)", getattr(user, "id", None))
        raise PermissionDenied("不正なアクセスです。")
    if role_obj is None:
        logger.warning(
            "role_objが取得できませんでした。",
            extra={
                "user_id": user.id,
                "raw_student_id": raw_student_id,
            }
            )
        raise PermissionDenied("不正なアクセスです。")

    # 4:) 管理者ブランチ
    if is_admin_or_teacher(user):
        student = get_object_or_404(Student.objects.active(), pk=raw_student_id)
        if not hasattr(role_obj, "can_manage_student") or not role_obj.can_manage_student(student):
            logger.warning(
                "アクセス権のない生徒に対するアクセス (user.id=%s, raw_student_id=%s)",
                getattr(user, "id", None),
                raw_student_id,
            )
            raise PermissionDenied("不正なアクセスです。")
        return student

    # 5:) 生徒ブランチ
    if is_student(user):
        student = role_obj
        if not isinstance(student, Student):
            logger.warning(
                "不正な生徒オブジェクトです。",
                extra={
                    "student_id": getattr(student, "id", None),
                    "raw_student_id": raw_student_id,
                }
                )
            raise PermissionDenied("不正なアクセスです。")
        if not student.is_active:
            logger.warning(
                "アクティブでない生徒にアクセスが試みられました。",
                extra={
                    "student_id": getattr(student, "id", None),
                    "raw_student_id": raw_student_id,
                }
            )
            raise Http404
        if str(raw_student_id) != str(student.id):
            logger.warning(
                "生徒が他人のstudent_idを指定してアクセスしようとしました (user.id=%s, raw_student_id=%s)",
                getattr(user, "id", None),
                raw_student_id
            )
            raise PermissionDenied("不正なアクセスです。")
        return student

    logger.warning(
        "想定外ロールのアクセスです。(user=%s, raw_student_id=%s)",
        user, raw_student_id
    )
    raise PermissionDenied("不正なアクセスです。")
