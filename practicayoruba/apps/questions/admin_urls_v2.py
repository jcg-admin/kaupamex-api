"""Admin URLs v2 — apps.questions (F3 migrar-urls-rest-v2)."""
from django.urls import path
from .views import AdminQuestionsListView, AdminQuestionAnswerView
from .views_v2 import QuestionStatusV2View

app_name = 'admin_questions_v2'

urlpatterns = [
    path('questions/', AdminQuestionsListView.as_view(), name='admin-list'),
    # Tier A rename: /answer/ → /answers/
    path('questions/<int:question_id>/answers/', AdminQuestionAnswerView.as_view(), name='admin-answers'),
    # Tier B: approve/reject → PATCH status
    path('questions/<int:question_id>/status/', QuestionStatusV2View.as_view(), name='admin-status'),
]
