"""URLs — ``addons.account_update_tax_tags``.

Un solo verbo (FBV) — ``path()`` directo, sin router. Ruta = PARTE 7C de
``uc-fin-11-actualizar-casillas-fiscales`` (montada bajo ``api/v2/admin/
finance/`` en ``config/urls.py``).
"""
from django.urls import path

from addons.account_update_tax_tags.controllers.views import recalculate_tax_tags

urlpatterns = [
    path('tax-tags/recalculate/', recalculate_tax_tags, name='recalculate-tax-tags'),
]
