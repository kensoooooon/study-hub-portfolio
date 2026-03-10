from typing import Optional
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404
import logging

from accounts.models import Student, BaseUser
from study_reminder.utils.is_check import is_student, is_admin_or_teacher

logger = logging.getLogger(__name__)

def student_access_check(user: BaseUser, raw_student_id: Optional[str]) -> Student:
    if not getattr(user, "is_authenticated", False):
        logger.warning("未認証ユーザーによるstudent_access_check呼び出し")
        raise PermissionDenied("不正なアクセスです。")

    if not raw_student_id:
        logger.warning("student_id が指定されていません。(user.id=%s)", getattr(user, "id", None))
        raise PermissionDenied("不正なアクセスです。")

    role_obj = user.get_role_object()
    if role_obj is None:
        logger.error("get_role_object が None でした。(user.id=%s, role=%s)", getattr(user, "id", None), getattr(user, "role", None))
        raise PermissionDenied("不正なアクセスです。")

    if is_admin_or_teacher(user):
        student = get_object_or_404(Student, pk=raw_student_id)
        if hasattr(role_obj, "can_manage_student") and not role_obj.can_manage_student(student):
            logger.warning("権限外の生徒アクセス (user.id=%s, student_id=%s)", getattr(user, "id", None), raw_student_id)
            raise PermissionDenied("この生徒にはアクセスできません。")
        return student

    if is_student(user):
        # role_obj が Student である前提を軽く担保
        if not isinstance(role_obj, Student):
            logger.error("studentロールなのにrole_objがStudentではありません。(user.id=%s)", getattr(user, "id", None))
            raise PermissionDenied("不正なアクセスです。")

        if str(raw_student_id) != str(role_obj.id):
            logger.warning("生徒が他人のstudent_idでアクセス (user.id=%s, raw_student_id=%s)", getattr(user, "id", None), raw_student_id)
            raise PermissionDenied("不正なアクセスです。")
        return role_obj

    logger.warning("想定外ロール (user.id=%s, role=%s)", getattr(user, "id", None), getattr(user, "role", None))
    raise PermissionDenied("不正なアクセスです。")
