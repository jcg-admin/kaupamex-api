"""URLs — apps.referral (UC-PRO-05). Montado bajo /api/v1/account/."""
from django.urls import path
from .views import ReferralView, RedeemReferralView

app_name = 'referral'

urlpatterns = [
    path('referral/', ReferralView.as_view(), name='referral'),
    path('referral/redeem/', RedeemReferralView.as_view(), name='referral-redeem'),
]
