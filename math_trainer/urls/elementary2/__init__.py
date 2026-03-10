from django.urls import include, path

app_name = "elementary2"

urlpatterns = [
    path('problem_select/', include('math_trainer.urls.elementary2.problem_select_urls')),
    path('display/', include('math_trainer.urls.elementary2.display_urls')),
    path('print/', include('math_trainer.urls.elementary2.print_urls')),
]
