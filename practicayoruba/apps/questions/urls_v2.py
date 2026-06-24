"""URLs v2 — apps.questions public (F3 migrar-urls-rest-v2)."""
from django.urls import path
from .views import ProductQuestionsView

app_name = 'questions_v2'

urlpatterns = [
    path('<int:product_id>/questions/', ProductQuestionsView.as_view(), name='product-questions'),
]
