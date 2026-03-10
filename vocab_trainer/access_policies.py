"""
vocab_trainerで利用するオブジェクトへのアクセス許可方針をまとめる
"""
from django.db.models import QuerySet, Q
from django.http import Http404
from django.shortcuts import get_object_or_404

import logging
from typing import Iterable, Optional, TypeVar, Type
import uuid

from accounts.models import BaseUser, Student, Teacher, ClassroomAdministrator, OrganizationAdministrator
from vocab_trainer.models import StudentContextProgress


logger = logging.getLogger(__name__)

# =========================================================
# 内部ユーティリティ
# =========================================================
def _get_first_param(request, keys: Iterable[str]) -> Optional[str]:
    """
    request から指定キー群を優先順で探索して最初に見つかった値を返す。
    kwargs post get の順で探索する。

    Note:
        - request.resolver_match が無い状況（テスト等）でも壊れないよう防御的に。
        - URLは設計で型や意味を確定させやすいため、最優先
            POST/GETはわずかにPOSTがマシだが、セキュリティ的には同じくらいの低い信頼性
            結局どちらもそこまで信用ならないので、外部でふわっと使わないこと
    """
    for k in keys:
        resolver_match = getattr(request, "resolver_match", None)
        if resolver_match and getattr(resolver_match, "kwargs", None):
            v = resolver_match.kwargs.get(k)
            if v:
                return v
        v = request.POST.get(k)
        if v:
            return v
        v = request.GET.get(k)
        if v:
            return v
    return None

# =========================================================
# A) 可視範囲 QuerySet
# =========================================================

T = TypeVar("T")

def _safe_role_obj(user: BaseUser, role: str, expected_type: Type[T]) -> Optional[T]:
    obj = user.get_role_object()
    if obj is None or not isinstance(obj, expected_type):
        logger.info(
            "role_obj missing or unexpected (user_id=%s role=%s obj=%s)",
            getattr(user, "id", None),
            role,
            type(obj).__name__ if obj is not None else None,
        )
        return None
    return obj


def visible_students_qs(user: BaseUser, base_qs: QuerySet[Student] | None = None) -> QuerySet[Student]:
    qs = base_qs if base_qs is not None else Student.objects.all()

    if not getattr(user, "is_active", False):
        return qs.none()

    if getattr(user, "is_superuser", False):
        return qs

    role = getattr(user, "role", None)

    if role == "student":
        role_obj = _safe_role_obj(user, role, Student)
        if role_obj is None:
            return qs.none()
        return qs.filter(id=role_obj.id)

    if role == "organization_administrator":
        role_obj = _safe_role_obj(user, role, OrganizationAdministrator)
        if role_obj is None:
            return qs.none()
        orgs = role_obj.organizations.all()
        return qs.filter(
            Q(organization__in=orgs)
            | Q(organization__isnull=True, classrooms__organization__in=orgs)
        ).distinct()

    if role == "classroom_administrator":
        role_obj = _safe_role_obj(user, role, ClassroomAdministrator)
        if role_obj is None:
            return qs.none()
        classrooms = role_obj.get_accessible_classrooms()
        return qs.filter(classrooms__in=classrooms).distinct()

    if role == "teacher":
        role_obj = _safe_role_obj(user, role, Teacher)
        if role_obj is None:
            return qs.none()
        students = role_obj.get_students().values_list("id", flat=True)
        return qs.filter(id__in=students)

    logger.warning(
        "想定しないロールのアクセスが発生しました。(user_id=%s role=%s)",
        getattr(user, "id", None),
        role,
    )
    return qs.none()



def visible_progress_qs(user: BaseUser, base_qs: QuerySet[StudentContextProgress] | None = None) -> QuerySet[StudentContextProgress]:
    """
    ユーザーがアクセス可能なStudentContextProgressを最大可視範囲で返す

    Args:
        user (BaseUser): 判定対象となるユーザー
        base_qs (QuerySet[StudentContextProgress] | None, optional): 判定の土台となる学習進捗群。与えられていないときは全体から取る

    Returns:
        QuerySet[StudentContextProgress]: 最大可視範囲の学習進捗群
    """
    if base_qs is not None:
        qs = base_qs
    else:
        qs = StudentContextProgress.objects.all()
    
    # 無効ユーザーは常に空（安全側）
    if not getattr(user, "is_active", False):
        return qs.none()

    # スーパーユーザーは全許可
    if getattr(user, "is_superuser", False):
        return qs
    
    # 生徒にアクセス可能=進捗にアクセス可能と捉える
    accessible_students = visible_students_qs(user)
    return qs.filter(student_id__in=accessible_students.values_list("id", flat=True))

# =========================================================
# B) id から単発取得（可視範囲QSから取って404）
# =========================================================
def get_accessible_student_by_uuid_or_404(user: BaseUser, student_id: uuid.UUID | str) -> Student:
    """UUIDを検証した後、該当する生徒を「可視範囲QS」から単発取得する。

    Args:
        user (BaseUser): 取得を試みているユーザー
        student_id (uuid.UUID | str): 取得したい生徒ID

    Raises:
        Http404: 可視範囲に存在しない、あるいはUUID形式に変換できない場合に送出

    Returns:
        (Student): 対象となる生徒
    """
    try:
        if isinstance(student_id, uuid.UUID):
            sid = student_id
        else:
            sid = uuid.UUID(str(student_id))
    except (ValueError, TypeError):
        raise Http404
    
    student = get_object_or_404(visible_students_qs(user), id=sid)
    return student


def get_accessible_progress_by_id_or_404(user: BaseUser, progress_id: int | str) -> StudentContextProgress:
    """
    IDで学習進捗を取得する。

    Args:
        user (BaseUser): 進捗を取得したいユーザー
        progress_id (int): 取得したい進捗のID

    Raise:
        Http404: 可視範囲に存在しない、もしくは進捗IDがint型と解釈できない場合に送出

    Returns:
        (StudentContextProgress): 対象の学習進捗
    """
    
    try:
        pid = int(progress_id)
    except (ValueError, TypeError):
        raise Http404
    
    progress = get_object_or_404(visible_progress_qs(user), id=pid)
    return progress


# =========================================================
# C) request から拾って、B を呼ぶ
# =========================================================
def get_accessible_student_or_404(request, student_id_name=None) -> Student:
    """requestからstudent_idを拾い、get_accessible_student_by_uuid_or_404を呼ぶ。

    Args:
        request : アクセスを求めてくるリクエスト
        student_id_name (str): テンプレートに設定された生徒のID名前

    Raises:
        Http404: 生徒IDが存在しないとき

    Returns:
        (Student): 対象となる生徒

    Note:
        改ざん可能入力の入口なので、失敗はすべて 404 に寄せる。
    """
    if student_id_name is None:
        raw_student_id = _get_first_param(request, keys=("student_id",))
    else:
        raw_student_id = _get_first_param(request, keys=(f"{student_id_name}",))
    if not raw_student_id:
        raise Http404

    return get_accessible_student_by_uuid_or_404(request.user, raw_student_id)


def get_accessible_progress_or_404(request) -> StudentContextProgress:
    """requestからprogress_idを拾い、get_accessible_progress_by_id_or_404を呼ぶ。

    Args:
        request: 進捗へのアクセスを求める情報が含まれるリクエスト
    
    Raises:
        Http404: 対象となる進捗IDがそもそも存在しない時

    Returns:
        (StudentContextProgress): 取得したい進捗
    """
    raw_progress_id = _get_first_param(request, keys=("progress_id",))
    if not raw_progress_id:
        raise Http404

    return get_accessible_progress_by_id_or_404(request.user, raw_progress_id)

# =========================================================
# bool判定系
# =========================================================

def student_can_be_accessed_by(user: BaseUser, student: Student) -> bool:
    """特定の生徒に対して、あるユーザーがアクセス可能かどうかを判定

    Args:
        user (BaseUser): 判定対象となるユーザー
        student (Student): アクセスしたい生徒

    Returns:
        (bool): アクセスの可否

    Note:
        既に Student オブジェクトがある状況で「アクセス可能か」を bool で返す。
        原則: 外部入力からの取得は get_accessible_*_or_404 / visible_*_qs を使う。
    """
    if not getattr(user, "is_active", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    # “可視範囲QSに含まれるか” で判定（DB1回）
    return visible_students_qs(user).filter(id=student.id).exists()

def progress_can_be_accessed_by(user: BaseUser, progress: StudentContextProgress) -> bool:
    """特定の進捗に対し、あるユーザーがアクセス可能かどうかの判定

    Args:
        user (BaseUser): 判定対象のユーザー
        progress (StudentContextProgress): アクセスしたい進捗

    Returns:
        bool: アクセスの可否
    """
    if not getattr(user, "is_active", False):  # アクティブでないユーザーはNG
        return False
    if getattr(user, "is_superuser", False):  # スーパーユーザーは即許可
        return True
    return visible_progress_qs(user).filter(id=progress.id).exists()  # DB側でチェックを入れる
