from django.urls import include, path

app_name = "junior_high2"

urlpatterns = [
    path('problem_select/', include('math_trainer.urls.junior_high2.problem_select_urls')),
    path('display/', include('math_trainer.urls.junior_high2.display_urls')),
    path('print/', include('math_trainer.urls.junior_high2.print_urls')),   
]
