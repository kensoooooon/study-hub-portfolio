from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.http import Http404

import logging
import uuid
from typing import Optional

from accounts.models import Student, BaseUser


logger = logging.getLogger(__name__)


def is_admin_or_teacher(user):
    return getattr(user, "role", None) in [
        "organization_administrator",
        "classroom_administrator",
        "teacher",
    ]


def is_student(user):
    return getattr(user, "role", None) == "student"


def get_role_object_or_403(user: BaseUser):
    """ロールオブジェクトの取得を試みて、正常に取得できなければ403を送出する

    Args:
        user (BaseUser): 取得対象となるユーザー

    Raises:
        PermissionDenied: get_role_object時に何かしらのエラーが発生
        PermissionDenied: role_objectがNoneで返ってきた

    Returns:
        role_obj: ユーザーのロールに基づいたロールオブジェクト(Student, Teacherなど)
    """
    try:
        role_obj = user.get_role_object()
    except Exception:
        logger.exception(
            "get_role_object に失敗しました。(user.id=%s)",
            getattr(user, "id", None),
        )
        raise PermissionDenied("不正なアクセスです。")

    if role_obj is None:
        logger.warning(
            "role_objが取得できませんでした。",
            extra={
                "user_id": getattr(user, "id", None),
            },
        )
        raise PermissionDenied("不正なアクセスです。")

    return role_obj


def ensure_can_access_student(user: BaseUser, student: Student) -> None:
    """あるユーザーが生徒にアクセス可能かをチェックし、問題があれば例外を送出するチェック用関数

    Args:
        user (BaseUser): 生徒を取得したいユーザー
        student (Student): 取得したい生徒

    Raises:
        - ロール判別前
            - PermissionDenied: 未ログインユーザーのアクセス
            - PermissionDenied: 実引数として渡された生徒が生徒でなかったとき
            - Http404: 対象生徒が非アクティブ
        - 講師もしくは管理職のとき
            - PermissionDenied: 管理職が持つはずの担当生徒判定用関数を持たないとき
            - PermissionDenied: 判定用関数が偽だったとき
        - 生徒のとき
            - PermissionDenied: 生徒ロールなのにStudentインスタンスではなかったとき
            - Http404: 対象生徒が非アクティブ
            - PermissionDenied: 唯一許可される自分自身へのアクセスではなかった場合
        - 想定外ロール
            - PermissionDenied: 想定外のロールだったとき
    """

    if not getattr(user, "is_authenticated", False):
        logger.warning("未認証ユーザーによるstudentアクセスチェック呼び出し")
        raise PermissionDenied("不正なアクセスです。")

    if not isinstance(student, Student):
        logger.warning(
            "studentではないオブジェクトが渡されました。",
            extra={
                "user_id": getattr(user, "id", None),
                "student_id": getattr(student, "id", None),
            },
        )
        raise PermissionDenied("不正なアクセスです。")

    if not student.is_active:
        logger.warning(
            "アクティブでない生徒にアクセスが試みられました。",
            extra={
                "user_id": getattr(user, "id", None),
                "student_id": getattr(student, "id", None),
            },
        )
        raise Http404

    role_obj = get_role_object_or_403(user)

    if is_admin_or_teacher(user):
        if not hasattr(role_obj, "can_manage_student"):
            logger.warning(
                "can_manage_studentを持たないrole_objです。",
                extra={
                    "user_id": getattr(user, "id", None),
                    "role": getattr(user, "role", None),
                    "student_id": getattr(student, "id", None),
                },
            )
            raise PermissionDenied("不正なアクセスです。")

        if not role_obj.can_manage_student(student):
            logger.warning(
                "アクセス権のない生徒に対するアクセス (user.id=%s, student_id=%s)",
                getattr(user, "id", None),
                getattr(student, "id", None),
            )
            raise PermissionDenied("不正なアクセスです。")

        return

    if is_student(user):
        if not isinstance(role_obj, Student):
            logger.warning(
                "不正な生徒ロールオブジェクトです。",
                extra={
                    "user_id": getattr(user, "id", None),
                    "role_obj_id": getattr(role_obj, "id", None),
                    "student_id": getattr(student, "id", None),
                },
            )
            raise PermissionDenied("不正なアクセスです。")

        if not role_obj.is_active:
            logger.warning(
                "アクティブでない生徒ユーザーによるアクセスです。",
                extra={
                    "user_id": getattr(user, "id", None),
                    "role_obj_id": getattr(role_obj, "id", None),
                },
            )
            raise Http404

        if str(role_obj.id) != str(student.id):
            logger.warning(
                "生徒が他人のstudent_idを指定してアクセスしようとしました (user.id=%s, student_id=%s)",
                getattr(user, "id", None),
                getattr(student, "id", None),
            )
            raise PermissionDenied("不正なアクセスです。")

        return

    logger.warning(
        "想定外ロールのアクセスです。(user=%s, student_id=%s)",
        user,
        getattr(student, "id", None),
    )
    raise PermissionDenied("不正なアクセスです。")


def student_access_check(user: BaseUser, raw_student_id: Optional[str]) -> Student:
    """与えられたIDの生徒がアクセス可能かをチェックし、生徒オブジェクトを返す

    Args:
        user (BaseUser): 取得を行いたいユーザー
        raw_student_id (Optional[str]): 取得対象の生徒ID

    Raises:
        PermissionDenied: 生徒IDがそもそも存在しない場合

    Returns:
        (Student): 対象生徒
    """

    if not raw_student_id:
        logger.warning(
            "student_id が指定されていません。(user.id=%s)",
            getattr(user, "id", None),
        )
        raise PermissionDenied("不正なアクセスです。")

    try:
        student_id = uuid.UUID(str(raw_student_id))  # uuidとして使える値にraw_student_idを変更し、それをUUIDに変換
    except (ValueError, TypeError, AttributeError):
        logger.warning(
            "不正な形式のstudent_idが指定されました。(user.id=%s, raw_student_id=%s)",
            getattr(user, "id", None),
            raw_student_id,
        )
        raise PermissionDenied("不正なアクセスです。")

    student = get_object_or_404(Student.objects.active(), pk=student_id)
    ensure_can_access_student(user, student)
    return student
