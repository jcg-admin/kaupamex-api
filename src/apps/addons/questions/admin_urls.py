"""Admin URLs — apps.addons.questions (UC-QST-03..04, F8 consolidation)."""
from django.urls import path
from .views import (
    AdminQuestionAnswerView,
    AdminQuestionsListView,
    QuestionStatusV2View,
)


app_name = 'admin_questions_v2'

urlpatterns = [
    path('questions/',
         AdminQuestionsListView.as_view(),
         name='admin-list'),
    path('questions/<int:question_id>/answers/',
         AdminQuestionAnswerView.as_view(),
         name='admin-answers'),
    path('questions/<int:question_id>/status/',
         QuestionStatusV2View.as_view(),
         name='admin-status'),
]
