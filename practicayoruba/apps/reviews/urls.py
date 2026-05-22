"""
URLs — apps.reviews (public side, mounted at /api/v1/products/).
"""
from django.urls import path
from .views import ProductReviewsView, ReviewHelpfulVoteView


app_name = 'reviews'

urlpatterns = [
    path('<int:product_id>/reviews/',
         ProductReviewsView.as_view(),
         name='product-reviews'),
    path('<int:product_id>/reviews/<int:pk>/helpful/',
         ReviewHelpfulVoteView.as_view(),
         name='review-helpful'),
]
