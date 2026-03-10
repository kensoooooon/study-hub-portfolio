from .auth_views import *
from .line_views import *
from .organization_admin_views import *
from .student_views import *

from django.shortcuts import render


def custom_permission_denied_view(request, exception=None):
    """
    PermissionDenied例外が発生した場合に表示するカスタムエラーページ
    """
    return render(request, '403.html', status=403)
