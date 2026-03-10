from django.urls import include, path

app_name = "junior_high1"

urlpatterns = [
    path('problem_select/', include('math_trainer.urls.junior_high1.problem_select_urls')),
    path('display/', include('math_trainer.urls.junior_high1.display_urls')),
    path('print/', include('math_trainer.urls.junior_high1.print_urls')),   
]
