from django.urls import path
from accounts.views import student_views

app_name = 'student'

urlpatterns = [
    path('home/', student_views.student_home, name='home'),
    path('english_history/', student_views.study_english_history, name='english_history'),
    path('chemical_history/', student_views.study_chemical_history, name='chemical_history'),
]
