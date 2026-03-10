from django.urls import path
from .views import process_reminders

# 管理画面作成用
from .views import ReminderListView, ReminderEditView, ReminderDeleteView, ReminderCreateView
# アコーディオン表示用
from .views import StudentListView, get_reminders_by_student


urlpatterns = [
    path('process-reminders/', process_reminders, name='process_reminders'),  # Google Cloud pub/subのトリガーポイント
    # 管理用のURL
    # path('', StudentListView.as_view(), name='student_list'),  # デフォルトビューを生徒一覧に
    path('manage/<int:pk>/edit/', ReminderEditView.as_view(), name='reminder_edit'),  # Edit
    path('manage/<int:pk>/delete/', ReminderDeleteView.as_view(), name='reminder_delete'),
    path('manage/create/', ReminderCreateView.as_view(), name='reminder_create'),
    # リマインダーのアコーディオン表示用
    path('students/', StudentListView.as_view(), name='student_list'),
    path('students/<uuid:student_id>/reminders/', get_reminders_by_student, name='get_reminders_by_student'),
    # リマインダー一覧を別URLに
    path('reminders/', ReminderListView.as_view(), name='reminder_list'),
]
