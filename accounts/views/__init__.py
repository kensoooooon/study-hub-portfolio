from .auth_views import CustomLoginView, CustomLogoutView
from .line_views import RegisterNameView
from .organization_admin_views import (
    ClassroomCreateView, 
    ClassroomEditView,
    ClassroomDeleteView,
    ClassroomListView,
    ClassroomDetailView,
    UnassignedStudentListView,
    ClassroomAssignmentView,
    StudentDetailView,
    StudentEditView,
    StudentDeleteView,
    TeacherDashboardView,
    TeacherEditView,
    TeacherCreateView,
    TeacherDeleteView,
    AccountEditView,
    StudentEditForTeachersView,
    StudentReactivateView,
)
from .student_views import (
    student_home,
    study_english_history,
    study_chemical_history,
)
from .ops_organization_views import (
    OrganizationListView,
    OrganizationDetailView,
    OrganizationCreateView,
    OrganizationAdminSelectView,
    OrganizationAssignAdminConfirmView,
    OrganizationAdminInvitationCreateView,
    OrganizationAdminInvitationAcceptView,
)

from django.shortcuts import render

__all__ = [
    "CustomLoginView",
    "CustomLogoutView",
    "RegisterNameView",
    "ClassroomCreateView",
    "ClassroomEditView",
    "ClassroomDeleteView",
    "ClassroomListView",
    "ClassroomDetailView",
    "UnassignedStudentListView",
    "ClassroomAssignmentView",
    "StudentDetailView",
    "StudentEditView",
    "StudentDeleteView",
    "TeacherDashboardView",
    "TeacherEditView",
    "TeacherCreateView",
    "TeacherDeleteView",
    "AccountEditView",
    "StudentEditForTeachersView",
    "student_home",
    "study_english_history",
    "study_chemical_history",
    "OrganizationListView",
    "OrganizationDetailView",
    "OrganizationCreateView",
    "OrganizationAdminSelectView",
    "OrganizationAssignAdminConfirmView",
    "OrganizationAdminInvitationCreateView",
    "OrganizationAdminInvitationAcceptView",
    "StudentReactivateView",
]


def custom_permission_denied_view(request, exception=None):
    """
    PermissionDenied例外が発生した場合に表示するカスタムエラーページ
    """
    return render(request, '403.html', status=403)
