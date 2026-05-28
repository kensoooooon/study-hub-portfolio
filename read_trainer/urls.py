from django.urls import path
from read_trainer.views import quiz_type_select_with_admin, AdminReadingQuizSolveView, AdminReadingQuizDispatcherView
from read_trainer.views import quiz_type_select_for_student, StudentReadingQuizSolveView, StudentReadingQuizDispatcherView

from read_trainer.views import eiken_quiz_type_select_with_admin, eiken_quiz_type_select_for_student

from read_trainer.views import admin_result_view, student_result_view

app_name = 'read_trainer'

urlpatterns = [
    ###
    # 管理者用
    ###
    # 出題タイプ選択画面(教科書)
    path('admin/quiz/type/', quiz_type_select_with_admin, name='quiz_type_select_with_admin'),
    # 出題タイプ選択画面(英検)
    path('admin/eiken_quiz/type/', eiken_quiz_type_select_with_admin, name='eiken_quiz_type_select_with_admin'),
    # 選択されたクイズごとの処理をひきうける
    path('admin/quiz/dispatch/', AdminReadingQuizDispatcherView.as_view(), name='quiz_admin_dispatch'),
    # 問題の出題と、解答画面へのリダイレクト
    path('admin/quiz/solve/<int:pk>/', AdminReadingQuizSolveView.as_view(), name='admin_solve'),
    # 解答画面の表示
    path("admin/quiz/result/", admin_result_view, name="admin_result"),
    ###
    # 生徒用
    ###
    path('student/quiz/type/', quiz_type_select_for_student, name='quiz_type_select_for_student'),
    path('student/eiken_quiz/type/', eiken_quiz_type_select_for_student, name='eiken_quiz_type_select_for_student'),
    path('student/quiz/dispatch/', StudentReadingQuizDispatcherView.as_view(), name='quiz_student_dispatch'),
    path('student/quiz/solve/<int:pk>/', StudentReadingQuizSolveView.as_view(), name='student_solve'),
    # 解答画面の表示
    path("student/quiz/result/", student_result_view, name="student_result"),
]
