# 現状管理用のため、利用予定なし
from django.urls import path
from conversations.views import StudentSummaryView

urlpatterns = [
    path('student_summary/<uuid:student_id>/', StudentSummaryView.as_view(), name='student_summary'),
]
