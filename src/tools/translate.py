"""i18n — fiel a ``odoo/tools/translate.py`` (Odoo 18/19).

Odoo expone ``_`` (y ``_lt``) desde ``odoo/tools/translate.py``. Aquí, con el
prefijo ``odoo.`` eliminado (convención del proyecto: ``tools`` ≙
``odoo/tools``), un addon escribe ``from tools.translate import _`` — leyendo
como su fuente Odoo (``from odoo.tools.translate import _``).

Respaldo Django: ``_`` = ``gettext_lazy`` (evaluación perezosa, como el ``_lt``
de Odoo, segura en definiciones de clase/módulo).
"""
from django.utils.translation import gettext_lazy as _

__all__ = ['_']
