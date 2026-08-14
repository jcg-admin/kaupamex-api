"""URLs — ``addons.account_check_printing``.

Un solo verbo (FBV) — ``path()`` directo, sin router (el router es sólo para
``ViewSet``, ver ``.claude/skills/backend-drf``). Ruta = PARTE 7C de
``uc-fin-09-imprimir-cheques-prenumerados`` (montada bajo ``api/v2/admin/
finance/`` en ``config/urls.py``).
"""
from django.urls import path

from addons.account_check_printing.controllers.views import print_checks

urlpatterns = [
    path('checks/print/', print_checks, name='print-checks'),
]
