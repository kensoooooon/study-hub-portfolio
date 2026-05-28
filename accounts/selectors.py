"""
可視範囲の組織・組織管理者クエリセットを規定

- ops_organization関連での操作に限定
- roleなどとは別枠として扱うこと
- 設計意識としてroleよりもpermissionを優先。groupは直接使わず、あくまで付与の枠組みに整えること
"""
from accounts.models import (
    Organization,
    OrganizationAdministrator,
    BaseUser,
    Student
    )


def visible_organizations_qs(user: BaseUser):
    if not user.is_authenticated:  # 未認証ユーザーは論外
        return Organization.objects.none()

    if not user.has_perm("accounts.view_organization"):  # 組織を見る権限がない場合
        return Organization.objects.none()

    if user.has_perm("accounts.view_all_organizations"):  # 全ての組織を見る場合
        return Organization.objects.all()

    if user.role != "organization_administrator":  # そもそも組織管理者ですらない場合はNG
        return Organization.objects.none()

    admin = user.get_role_object()
    if admin is None:
        return Organization.objects.none()

    return admin.get_accessible_organizations()


def visible_organization_administrators_qs(user: BaseUser):
    if not user.is_authenticated:  # 未認証ユーザーは論外
        return OrganizationAdministrator.objects.none()

    if not user.has_perm("accounts.view_organizationadministrator"):  # 管理者を見る権限を持たない場合
        return OrganizationAdministrator.objects.none()

    if user.has_perm("accounts.view_all_organization_administrators"):  # 全組織管理者を見れる場合
        return OrganizationAdministrator.objects.all()

    if user.role != "organization_administrator":  # 組織管理者でない場合はNG
        return OrganizationAdministrator.objects.none()

    admin = user.get_role_object()
    if admin is None:
        return OrganizationAdministrator.objects.none()

    return OrganizationAdministrator.objects.filter(
        organizations__in=admin.get_accessible_organizations()
    ).distinct()


def visible_students_qs(user: BaseUser):
    """ユーザーごとに最大可視範囲の生徒を返す

    Args:
        user (BaseUser): 判定の対象となるユーザー

    Returns:
        (Queryset): 最大可視範囲の生徒 
    """
    if not user.is_authenticated:  # 未認証ユーザーは仮にアクセスされても弾く
        return Student.objects.none()
    
    if user.role == "student":  # 生徒には生徒を見せない
        return Student.objects.none()

    qs = Student.objects.active()  # アクティブな生徒を取得
    role_object = user.get_role_object()
    
    if role_object is None:  # 職能にアクセスできるオブジェクトが存在しない
        return Student.objects.none()

    if user.role == "teacher":  # 担任の先生になる生徒だけ見せる
        qs = qs.filter(teachers=role_object)
        if role_object.organization:
            qs = qs.filter(organization=role_object.organization)  # 組織がある場合はその範囲で
        return qs.distinct()

    if user.role == "classroom_administrator":  # 生徒が所属している教室の管理者にだけ見せる
        qs = qs.filter(classrooms__in=role_object.get_accessible_classrooms()).distinct()
        return qs
    
    if user.role == "organization_administrator":  # 生徒が所属している組織の管理者にだけ見せる
        qs = qs.filter(organization__in=role_object.get_accessible_organizations()).distinct()
        return qs
    return Student.objects.none()  # どれにも当てはまらない場合は安全側に倒す


def get_visible_self_student(user: BaseUser):
    """生徒本人に対応するアクティブな Student を返す
    
    Args:
        user (BaseUser): 対象となるユーザー
    """
    if not user.is_authenticated:
        return None

    if user.role == "student":
        return Student.objects.active().filter(pk=user.pk).first()

    return None

def visible_inactive_students_qs(user: BaseUser):
    """そのユーザーに見せていい範囲で非アクティブな生徒を出力する

    why:
        生徒復旧

    concerns:
        - 今回の復旧では教師を弾くが、それはここでの仕事では多分ない。
        dispatchで仕事してもらって、ここではあくまで最大可視範囲の非アクティブ生徒を見せること
    """
    if not user.is_authenticated:  # 未認証ユーザーは仮にアクセスされても弾く
        return Student.objects.none()
    
    if user.role == "student":  # 生徒には生徒を見せない
        return Student.objects.none()

    qs = Student.objects.inactive()  # アクティブな生徒を取得
    role_object = user.get_role_object()
    
    if role_object is None:  # 職能にアクセスできるオブジェクトが存在しない
        return Student.objects.none()

    if user.role == "teacher":  # 担任の先生になる生徒だけ見せる
        qs = qs.filter(teachers=role_object)
        if role_object.organization:
            qs = qs.filter(organization=role_object.organization)  # 組織がある場合はその範囲で
        return qs.distinct()

    if user.role == "classroom_administrator":  # 生徒が所属している教室の管理者にだけ見せる
        qs = qs.filter(classrooms__in=role_object.get_accessible_classrooms()).distinct()
        return qs
    
    if user.role == "organization_administrator":  # 生徒が所属している組織の管理者にだけ見せる
        qs = qs.filter(organization__in=role_object.get_accessible_organizations()).distinct()
        return qs
    return Student.objects.none()  # どれにも当てはまらない場合は安全側に倒す
