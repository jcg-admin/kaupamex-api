"""URLs admin — moderación de reseñas (``rating``). Montado en /api/v2/admin/."""
from django.urls import path

from addons.rating.controllers.main import ReviewAdminListView, ReviewStatusV2View

app_name = 'admin_reviews_v2'

urlpatterns = [
    path('reviews/', ReviewAdminListView.as_view(), name='reviews-list'),
    path('reviews/<int:pk>/status/', ReviewStatusV2View.as_view(),
         name='admin-status'),
]
