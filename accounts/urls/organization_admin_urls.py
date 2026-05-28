from django.urls import path
from accounts.views import ClassroomListView, ClassroomDetailView, StudentDetailView
from accounts.views import StudentEditView, TeacherDashboardView
from accounts.views import TeacherEditView, TeacherCreateView, TeacherDeleteView
from accounts.views import ClassroomCreateView, ClassroomEditView, ClassroomDeleteView
from accounts.views import UnassignedStudentListView, ClassroomAssignmentView
from accounts.views import AccountEditView
from accounts.views import StudentEditForTeachersView

from accounts.views import StudentDeleteView
from accounts.views import StudentReactivateView

app_name = 'organization_admin'

urlpatterns = [
    path('classrooms/', ClassroomListView.as_view(), name='classroom_list'),
    path('classrooms/<int:pk>/', ClassroomDetailView.as_view(), name='classroom_detail'),
    path('classrooms/add/', ClassroomCreateView.as_view(), name='classroom_add'),
    path('classrooms/<int:pk>/edit/', ClassroomEditView.as_view(), name='classroom_edit'),
    path('classrooms/<int:pk>/delete/', ClassroomDeleteView.as_view(), name='classroom_delete'),
    path("unassigned_students/", UnassignedStudentListView.as_view(), name="unassigned_students"),
    path("assign_classroom/<uuid:pk>/", ClassroomAssignmentView.as_view(), name="assign_classroom"),
    path('students/<uuid:pk>/', StudentDetailView.as_view(), name='student_detail'),
    path('students/<uuid:pk>/edit/', StudentEditView.as_view(), name='student_edit'),  
    path('teacher_dashboard/', TeacherDashboardView.as_view(), name='teacher_dashboard'),  # 講師用の管理画面
    path('teachers/<uuid:pk>/edit/', TeacherEditView.as_view(), name='teacher_edit'),
    path('teachers/add/', TeacherCreateView.as_view(), name='teacher_add'),  # 追加用のビューも実装可能
    path('teachers/<uuid:pk>/delete/', TeacherDeleteView.as_view(), name='teacher_delete'),
    path('account/edit/', AccountEditView.as_view(), name='account_edit'),  # 自身のアカウント編集用
    path('students/<uuid:pk>/edit_for_teachers/', StudentEditForTeachersView.as_view(), name='student_edit_for_teachers'),  # 講師用の教科書とメルアド編集用
    path('students/<uuid:pk>/delete/', StudentDeleteView.as_view(), name='student_delete'),
    path('classrooms/<int:classroom_id>/reactivate_students/', StudentReactivateView.as_view(), name='student_reactivate'),  # 教室単位で生徒を最アクティブさせる
]