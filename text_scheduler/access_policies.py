"""
text_scheduler/access_policies.py

アクセス制御を集中的に管理するモジュール。

設計方針:
A) 可視範囲 QuerySet を返す (visible_*_qs)
B) id を引数に取り、可視範囲QSから単発取得して 404 (get_accessible_*_by_*_or_404)
C) request から id を拾って型変換し、B を呼ぶ (get_accessible_*_or_404)

※ 改ざん可能なID入力（URL/GET/POST/hiddenなど）を前提に、存在/権限なしは 404 で統一。

使い所:
A（visible_*_qs）
MaterialAccessMixin.get_queryset() → visible_materials_qs(request.user)
将来の「生徒検索」「生徒一覧」ビュー → visible_students_qs(request.user)

B（get_accessible_by_or_404）
kwargs などですでに id が確定している場面（dispatch / get_object）
get_accessible_material_by_id_or_404(user, material_id)
get_accessible_student_by_uuid_or_404(user, student_uuid)

C（get_accessible_*_or_404）
URL/GET/POSTから拾う入口（改ざん可能）
StudyLogCreateView.dispatch などで get_accessible_student_or_404(request) / get_accessible_material_or_404(request)
"""

from __future__ import annotations

import logging
import uuid
from typing import Iterable, Optional, Type, TypeVar

from django.db.models import QuerySet, Q
from django.http import Http404
from django.shortcuts import get_object_or_404

from accounts.models import BaseUser, Student, Teacher, ClassroomAdministrator, OrganizationAdministrator
from .models import LearningMaterial

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
        return qs.filter(Q(organization__in=orgs)).distinct()

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




def visible_materials_qs(user: BaseUser, base_qs: QuerySet[LearningMaterial] | None = None) -> QuerySet[LearningMaterial]:
    """
    user が閲覧可能な LearningMaterial の QuerySet を返す（最大範囲）。

    Args:
        user (BaseUser): 判定対象となるユーザー
        base_qs (QuerySet[LearningMaterial] | None, optional): 判定のベースとなる教材群。与えられていないときは全体から取る

    Returns:
        QuerySet[LearningMaterial]: 最大可視範囲の教材群

    Note:
        - 生徒が見える=教材も見えるという判定
        - student の可視範囲QSを起点にすることで、ロジックの一貫性を保つ。
        - target_student をよく参照するため select_related を標準で付与しても良い。
        （必要なら呼び出し側でさらに select_related/prefetch_related を追加）
    """
    qs = base_qs if base_qs is not None else LearningMaterial.objects.all()

    # 無効ユーザーは常に空（安全側）
    if not getattr(user, "is_active", False):
        return qs.none()

    # スーパーユーザーは全許可
    if getattr(user, "is_superuser", False):
        return qs

    # 学生可視範囲を subquery で絞る（DB側で処理される）
    accessible_students = visible_students_qs(user)
    # return qs.filter(target_student__in=students_qs)
    return qs.filter(target_student_id__in=accessible_students.values_list("id", flat=True))


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


def get_accessible_material_by_id_or_404(user: BaseUser, material_id: int | str) -> LearningMaterial:
    """intのmaterial_idが与えられた状態で、教材を「可視範囲QS」から単発取得する。

    Args:
        user (BaseUser): 教材を取得したいユーザー
        material_id (int | str): 取得したい教材のID

    Raises:
        Http404: 可視範囲に存在しない、または正しくint型のIDに出来ないときに送出

    Returns:
        (LearningMaterial): 対象の教材 
    """

    try:
        mid = int(material_id)  # material は UUID ではない前提
    except (ValueError, TypeError):
        raise Http404
    material = get_object_or_404(visible_materials_qs(user), id=mid)
    return material


# =========================================================
# C) requestから拾って、Bを呼ぶ
# =========================================================
def get_accessible_student_or_404(request) -> Student:
    """request から student_id を拾い、UUIDに変換してから B を呼ぶ。

    Args:
        request (_type_): アクセスを求めてくるリクエスト

    Raises:
        Http404: 生徒IDが存在しないとき

    Returns:
        (Student): 対象となる生徒

    Note:
        改ざん可能入力の入口なので、失敗はすべて 404 に寄せる。
    """
    raw_student_id = _get_first_param(request, keys=("student_id",))
    if not raw_student_id:
        raise Http404

    return get_accessible_student_by_uuid_or_404(request.user, raw_student_id)


def get_accessible_material_or_404(request) -> LearningMaterial:
    """request から material_id（int）を拾ってB を呼ぶ。

    Args:
        request: 教材へのアクセスを求めてくるリクエスト

    Raises:
        Http404: 教材IDが存在しない時

    Returns:
        (LearningMaterial)取得したい教材
    """
    raw_material_id = _get_first_param(request, keys=("material_id", "pk"))
    if not raw_material_id:
        raise Http404

    return get_accessible_material_by_id_or_404(request.user, raw_material_id)


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


def material_can_be_accessed_by(user: BaseUser, material: LearningMaterial) -> bool:
    """特定の教材に対して、あるユーザーがアクセス可能かどうかを判定

    Args:
        user (BaseUser): 判定対象となるユーザー
        material (LearningMaterial): アクセスしたい教材

    Returns:
        bool: アクセスの可否
    
    Note:
        既に LearningMaterial オブジェクトがある状況で「アクセス可能か」を bool で返す
        原則: 外部入力からの取得は get_accessible_*_or_404 / visible_*_qs を使う。
    """
    if not getattr(user, "is_active", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return visible_materials_qs(user).filter(id=material.id).exists()
