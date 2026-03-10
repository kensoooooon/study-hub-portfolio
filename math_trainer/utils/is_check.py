"""
ユーザーのロールを判定するヘルパー関数
"""
def is_admin_or_teacher(user):
    if hasattr(user, "role"):
        if user.role in ["organization_administrator", "classroom_administrator", "teacher"]:
            return True
    return False


def is_student(user):
    if hasattr(user, "role"):
        if user.role == "student":
            return True
    return False