from django.urls import path
from listening_trainer.views import quiz_type_select_with_admin, AdminListeningQuizSolveView, AdminListeningQuizDispatcherView
from listening_trainer.views import quiz_type_select_for_student, StudentListeningQuizSolveView, StudentListeningQuizDispatcherView

from listening_trainer.views import eiken_quiz_type_select_with_admin, eiken_quiz_type_select_for_student, admin_result_view, student_result_view

app_name = 'listening_trainer'

urlpatterns = [
    ###
    # 管理者用
    ###
    # 出題タイプ選択画面(教科書)
    path('admin/quiz/type/', quiz_type_select_with_admin, name='quiz_type_select_with_admin'),
    # 出題タイプ選択画面(英検)
    path('admin/eiken_quiz/type/', eiken_quiz_type_select_with_admin, name='eiken_quiz_type_select_with_admin'),
    # 選択されたクイズごとの処理をひきうける
    path('admin/quiz/dispatch/', AdminListeningQuizDispatcherView.as_view(), name='quiz_admin_dispatch'),
    # 解答後の採点、記録処理
    path("admin/quiz/result/", admin_result_view, name="admin_result"),
    # 解答画面（新規・既存共通）
    path('admin/quiz/solve/<int:pk>/', AdminListeningQuizSolveView.as_view(), name='admin_solve'),
    ###
    # 生徒用
    ###
    path('student/quiz/type', quiz_type_select_for_student, name='quiz_type_select_for_student'),
    path('student/eiken_quiz/type', eiken_quiz_type_select_for_student, name='eiken_quiz_type_select_for_student'),
    path('student/quiz/dispatch/', StudentListeningQuizDispatcherView.as_view(), name='quiz_student_dispatch'),
    path("student/quiz/result/", student_result_view, name="student_result"),
    path('student/quiz/solve/<int:pk>/', StudentListeningQuizSolveView.as_view(), name='student_solve'),
]
