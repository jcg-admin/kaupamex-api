"""URLs de checkout express — addons.payments (Sprint 15, UC-ORD-01-EXT)."""
from django.urls import path
from .views import CheckoutEligibilityView, ExpressCheckoutView

urlpatterns = [
    path('eligibility/', CheckoutEligibilityView.as_view(), name='checkout-eligibility'),
    path('express/',     ExpressCheckoutView.as_view(),     name='checkout-express'),
]
