"""
Admin URLs — addons.reviews (F8 consolidation). Mounted at /api/v2/admin/.
"""
from django.urls import path
from .views import ReviewAdminListView, ReviewStatusV2View


app_name = 'admin_reviews_v2'

urlpatterns = [
    path('reviews/',              ReviewAdminListView.as_view(),
         name='reviews-list'),
    path('reviews/<int:pk>/status/', ReviewStatusV2View.as_view(), name='admin-status'),
]
