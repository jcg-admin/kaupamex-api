"""
URLs — apps.referral (F8 consolidation).

Mounted in config/urls.py:
  path('api/v2/account/', include(('apps.referral.urls', 'referral'), namespace='referral_v2'))
"""
from django.urls import path
from .views import ReferralView, RedeemReferralView

app_name = 'referral'

urlpatterns = [
    path('referral/', ReferralView.as_view(), name='referral'),
    path('referral/redemptions/', RedeemReferralView.as_view(), name='referral-redemptions'),
]
