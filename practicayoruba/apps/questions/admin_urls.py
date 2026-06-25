"""Admin URLs — apps.questions (UC-QST-03..04, F8 consolidation)."""
from django.urls import path
from .views import (
    AdminQuestionAnswerView,
    AdminQuestionApproveView,
    AdminQuestionRejectView,
    AdminQuestionsListView,
    QuestionStatusV2View,
)


app_name = 'admin_questions'

urlpatterns = [
    path('questions/',
         AdminQuestionsListView.as_view(),
         name='admin-list'),
    path('questions/<int:question_id>/answer/',
         AdminQuestionAnswerView.as_view(),
         name='admin-answer'),
    path('questions/<int:question_id>/approve/',
         AdminQuestionApproveView.as_view(),
         name='admin-approve'),
    path('questions/<int:question_id>/reject/',
         AdminQuestionRejectView.as_view(),
         name='admin-reject'),
    path('questions/<int:question_id>/answers/',
         AdminQuestionAnswerView.as_view(),
         name='admin-answers'),
    path('questions/<int:question_id>/status/',
         QuestionStatusV2View.as_view(),
         name='admin-status'),
]
