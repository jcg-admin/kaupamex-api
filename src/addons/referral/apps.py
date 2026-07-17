"""AppConfig — addons.referral (UC-PRO-05: programa de referidos)."""
from django.apps import AppConfig


class ReferralConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.referral'
    verbose_name = 'Programa de referidos'
