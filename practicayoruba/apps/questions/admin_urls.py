"""Admin URLs — apps.questions (UC-QST-03..04)."""
from django.urls import path
from .views import AdminQuestionAnswerView, AdminQuestionApproveView, AdminQuestionRejectView, AdminQuestionsListView


app_name = 'admin_questions_v2'

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
]
