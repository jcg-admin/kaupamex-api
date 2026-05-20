"""URLs — apps.questions (public endpoints, mounted under /api/v1/products/)."""
from django.urls import path
from .views import ProductQuestionsView


app_name = 'questions'

urlpatterns = [
    path('<int:product_id>/questions/',
         ProductQuestionsView.as_view(),
         name='product-questions'),
]
