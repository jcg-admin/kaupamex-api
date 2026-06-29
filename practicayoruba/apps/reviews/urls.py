"""
URLs — apps.reviews public (F8 consolidation).

Mounted in config/urls.py:
  path('api/v2/products/', include(('apps.reviews.urls', 'reviews'), namespace='reviews_v2'))
"""
from django.urls import path
from .views import ProductReviewsView, ReviewHelpfulVoteView, ReviewImageCreateView, ReviewUpdateView

app_name = 'reviews_v2'

urlpatterns = [
    path('<int:product_id>/reviews/', ProductReviewsView.as_view(), name='product-reviews'),
    path('<int:product_id>/reviews/<int:pk>/', ReviewUpdateView.as_view(), name='review-detail'),
    path('<int:product_id>/reviews/<int:pk>/helpful-votes/', ReviewHelpfulVoteView.as_view(), name='review-helpful-votes'),
    path('<int:product_id>/reviews/<int:pk>/images/', ReviewImageCreateView.as_view(), name='review-images'),
]
