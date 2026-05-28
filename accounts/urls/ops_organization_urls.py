from django.urls import path, include


from accounts.views import (
    OrganizationListView, OrganizationDetailView, OrganizationCreateView,
    OrganizationAdminSelectView, OrganizationAssignAdminConfirmView,
    OrganizationAdminInvitationCreateView, OrganizationAdminInvitationAcceptView
)

app_name = "ops_organization"


urlpatterns = [
    path('organizations/list/', OrganizationListView.as_view(), name="list"),
    path('organizations/<int:pk>/', OrganizationDetailView.as_view(), name="detail"),
    path('organizations/create/', OrganizationCreateView.as_view(), name="create"),
    path('organizations/<int:pk>/assign_admin/', OrganizationAdminSelectView.as_view(), name="assign_admin"),
    path('organizations/<int:pk>/assign_admin/confirm', OrganizationAssignAdminConfirmView.as_view(), name="assign_admin_confirm"),
    path("organizations/<int:organization_id>/org-admin-invitations/create/", OrganizationAdminInvitationCreateView.as_view(), name="create_admin_invitation"),  # 組織管理者を作成するビューと紐 
    path("invitations/accept/", OrganizationAdminInvitationAcceptView.as_view(), name="accept_org_admin_invitation"),  # 踏まれるURL(トークンつきの予定)
    path("organizations/<int:org_pk>/line-channels/", include(("line_channels.urls.org_urls", "org_line_channels"), namespace="org_line_channels"),)  # 派生元はこちら。委託先はあちらの精神
]
