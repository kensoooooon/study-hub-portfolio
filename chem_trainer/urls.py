from django.urls import path
from chem_trainer.views import elemental_quiz, substance_quiz, compound_quiz, equation_quiz, random_quiz, review_quiz
from chem_trainer.views import check_answer
from chem_trainer.views import study_card

app_name = 'chem_trainer'

urlpatterns = [
    path('elemental_quiz/', elemental_quiz, name='elemental_quiz'),
    path('substance_quiz/', substance_quiz, name='substance_quiz'),
    path('compound_quiz/', compound_quiz, name='compound_quiz'),
    path('equation_quiz/', equation_quiz, name='equation_quiz'),
    path('random_quiz/', random_quiz, name='random_quiz'),
    path('review_quiz/', review_quiz, name='review_quiz'),
    path('check_answer/', check_answer, name='check_answer'),
    path('study_card/<str:type>/<int:relation_id>/', study_card, name='study_card'),
    # path('study_card/', study_card, name='study_card'),
]