from .admin_views import (
    quiz_type_select_with_admin,
    eiken_quiz_type_select_with_admin,
    AdminListeningQuizDispatcherView,
    AdminListeningQuizSolveView,
    admin_result_view,
)

from .student_views import (
    quiz_type_select_for_student,
    eiken_quiz_type_select_for_student,
    StudentListeningQuizDispatcherView,
    StudentListeningQuizSolveView,
    student_result_view,
)

__all__ = [
    # 管理者用
    "quiz_type_select_with_admin",
    "eiken_quiz_type_select_with_admin",
    "AdminListeningQuizDispatcherView",
    "AdminListeningQuizSolveView",
    "admin_result_view",
    # 生徒用
    "quiz_type_select_for_student",
    "eiken_quiz_type_select_for_student",
    "StudentListeningQuizDispatcherView",
    "StudentListeningQuizSolveView",
    "student_result_view",
]
