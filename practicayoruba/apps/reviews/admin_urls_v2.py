"""Admin URLs v2 — apps.reviews (F3 migrar-urls-rest-v2)."""
from django.urls import path
from .views import ReviewAdminListView
from .views_v2 import ReviewStatusV2View

app_name = 'admin_reviews_v2'

urlpatterns = [
    path('reviews/', ReviewAdminListView.as_view(), name='admin-list'),
    # Tier B: approve/reject → PATCH status
    path('reviews/<int:pk>/status/', ReviewStatusV2View.as_view(), name='admin-status'),
]
