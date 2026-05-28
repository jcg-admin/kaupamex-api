"""
URLs — apps.reviews (public side, mounted at /api/v1/products/).
"""
from django.urls import path
from .views import (
    ProductReviewsView, ReviewHelpfulVoteView,
    ReviewImageCreateView, ReviewUpdateView,
)


app_name = 'reviews'

urlpatterns = [
    path('<int:product_id>/reviews/',
         ProductReviewsView.as_view(),
         name='product-reviews'),
    path('<int:product_id>/reviews/<int:pk>/helpful/',
         ReviewHelpfulVoteView.as_view(),
         name='review-helpful'),
    path('<int:product_id>/reviews/<int:pk>/edit/',
         ReviewUpdateView.as_view(),
         name='review-edit'),
    path('<int:product_id>/reviews/<int:pk>/images/',
         ReviewImageCreateView.as_view(),
         name='review-image-create'),
]
