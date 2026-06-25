"""
Admin URLs — apps.reviews (F8 consolidation). Mounted at /api/v1/admin/.
"""
from django.urls import path
from .views import ReviewAdminListView, ReviewApproveView, ReviewRejectView, ReviewStatusV2View


app_name = 'admin_reviews'

urlpatterns = [
    path('reviews/',              ReviewAdminListView.as_view(),
         name='reviews-list'),
    path('reviews/<int:pk>/approve/', ReviewApproveView.as_view(),
         name='reviews-approve'),
    path('reviews/<int:pk>/reject/',  ReviewRejectView.as_view(),
         name='reviews-reject'),
    path('reviews/<int:pk>/status/', ReviewStatusV2View.as_view(), name='admin-status'),
]
