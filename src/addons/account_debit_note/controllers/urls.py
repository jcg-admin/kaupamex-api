"""URLs — ``addons.account_debit_note``.

Un solo verbo (FBV) — ``path()`` directo, sin router. Ruta = PARTE 7C de
``uc-fin-10-crear-nota-de-debito`` (montada bajo ``api/v2/admin/finance/``
en ``config/urls.py``).
"""
from django.urls import path

from addons.account_debit_note.controllers.views import create_debit_note

urlpatterns = [
    path('debit-notes/', create_debit_note, name='create-debit-note'),
]
