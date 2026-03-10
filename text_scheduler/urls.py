from django.urls import path
from text_scheduler.views.materials import (
    LearningMaterialListView,
    LearningMaterialCreateView,
    LearningMaterialUpdateView,
    LearningMaterialDeleteView,
    material_plan_preview
)
from text_scheduler.views.study_log import StudyLogCreateView, StudyLogBulkCreateView

app_name = "text_scheduler"

urlpatterns = [
    path("materials/list/", LearningMaterialListView.as_view(), name="material_list"),
    path("materials/create/<uuid:student_id>/", LearningMaterialCreateView.as_view(), name="material_create"),
    path("materials/<int:pk>/edit/", LearningMaterialUpdateView.as_view(), name="material_edit"),
    path("materials/<int:pk>/delete/", LearningMaterialDeleteView.as_view(), name="material_delete"),
    path("studylogs/create/<uuid:student_id>/<int:material_id>/", StudyLogCreateView.as_view(), name="studylog_create"),
    path("studylogs/bulk/<uuid:student_id>/<int:material_id>/",  StudyLogBulkCreateView.as_view(), name="studylog_bulk_create"),
    path("materials/plan_preview/", material_plan_preview, name="material_plan_preview"),
]
