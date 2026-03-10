from django.urls import path
from vocab_trainer.views.card import study_card

from vocab_trainer.views.quiz.for_student.check_answer import check_answer_for_student
from vocab_trainer.views.quiz.for_student.quiz_all import quiz_all_for_student
from vocab_trainer.views.quiz.for_student.quiz_chapter import quiz_chapter_for_student
from vocab_trainer.views.quiz.for_student.quiz_review import quiz_review_for_student
from vocab_trainer.views.quiz.for_student.quiz_type_select import quiz_type_select_for_student

from vocab_trainer.views.update_review_priority import update_review_priority

from vocab_trainer.views.quiz.for_admin.quiz_type_select import quiz_type_select_with_admin
from vocab_trainer.views.quiz.for_admin.quiz_all import quiz_all_with_admin
from vocab_trainer.views.quiz.for_admin.quiz_chapter import quiz_chapter_with_admin
from vocab_trainer.views.quiz.for_admin.quiz_review import quiz_review_with_admin
from vocab_trainer.views.quiz.for_admin.check_answer import check_answer_with_admin


app_name = 'vocab_trainer'


urlpatterns = [
    ## 生徒用
    # ✅ クイズの種類選択
    path('quiz/type/', quiz_type_select_for_student, name='quiz_type_select_for_student'),
    # ✅ 教科書全体からのクイズ
    path('quiz/all/', quiz_all_for_student, name='quiz_all_for_student'),
    # ✅ 特定チャプターからのクイズ
    path('quiz/chapter/', quiz_chapter_for_student, name='quiz_chapter_for_student'),
    # ✅ 復習クイズ
    path('quiz/review/', quiz_review_for_student, name='quiz_review_for_student'),
    # ✅ 回答のチェック
    path('check_answer/', check_answer_for_student, name='check_answer_for_student'),
    # ✅ 学習カード
    path('study/<int:progress_id>/', study_card, name='study_card'),
    # ✅ 復習優先度再計算エンドポイント
    path('update-review-priority/', update_review_priority, name='update_review_priority'),
    ## 講師,および管理者用
    # クイズの種類選択
    path('admin_quiz/type/', quiz_type_select_with_admin, name='quiz_type_select_with_admin'),
    # 管理者・講師用クイズ
    path('admin_quiz/all/', quiz_all_with_admin, name='quiz_all_with_admin'),
    path('admin_quiz/chapter/', quiz_chapter_with_admin, name='quiz_chapter_with_admin'),
    path('admin_quiz/review/', quiz_review_with_admin, name='quiz_review_with_admin'),
    path('admin_quiz/check_answer/', check_answer_with_admin, name='check_answer_with_admin'),
]
