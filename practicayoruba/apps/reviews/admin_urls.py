"""
Admin URLs — apps.reviews. Mounted at /api/v1/admin/.
"""
from django.urls import path
from .views import ReviewAdminListView, ReviewApproveView, ReviewRejectView


app_name = 'admin_reviews_v2'

urlpatterns = [
    path('reviews/',              ReviewAdminListView.as_view(),
         name='reviews-list'),
    path('reviews/<int:pk>/approve/', ReviewApproveView.as_view(),
         name='reviews-approve'),
    path('reviews/<int:pk>/reject/',  ReviewRejectView.as_view(),
         name='reviews-reject'),
]
