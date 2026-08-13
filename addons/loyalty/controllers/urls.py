"""URLs del programa de referidos — ``loyalty``.

Montado en ``config/urls.py``::

    path('api/v2/account/referral/', include((
        'addons.loyalty.controllers.urls', 'referral'),
        namespace='referral_v2'))

Cuelga de ``account/`` porque es superficie de cuenta propia, igual que la
capacidad que la gatea (``account.referral``).
"""
from django.urls import path

from addons.loyalty.controllers.referral import (
    redeem_referral,
    referral_program,
)

app_name = 'referral'

urlpatterns = [
    path('', referral_program, name='referral-program'),
    path('redemptions/', redeem_referral, name='referral-redemptions'),
]
