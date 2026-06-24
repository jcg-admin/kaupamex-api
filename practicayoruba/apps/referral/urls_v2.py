"""URLs — apps.referral v2 (F2). Montado bajo /api/v2/account/."""
from django.urls import path

from .views import ReferralView, RedeemReferralView

app_name = 'referral_v2'

urlpatterns = [
    path('referral/',             ReferralView.as_view(),        name='referral'),
    path('referral/redemptions/', RedeemReferralView.as_view(),  name='referral-redemptions'),
]
