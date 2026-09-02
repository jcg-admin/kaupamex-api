"""Extensión de ``res.country`` — ¿hay posición fiscal extranjera en este país?

Adaptación de ``odoo19c: addons/base_vat/models/res_country.py``
(``odoo-tools@622ddc2a``, LGPL-3, 18 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03). Mecanismo: **copia + adaptación**, que es lo que su
manifiesto (``LGPL-3``) autoriza.

Porte — 3 de 3 símbolos, 0 bloqueados
======================================

.. list-table::
   :header-rows: 1
   :widths: 44 14 42

   * - Símbolo (línea)
     - Estado
     - Nota
   * - ``_inherit = 'res.country'`` (``:7``)
     - portado
     - lo expresa ``extend_model``
   * - ``has_foreign_fiscal_position`` (``:9``)
     - portado
     - ``compute`` **sin** ``store`` → ``propiedades=`` (``property``)
   * - ``_compute_has_foreign_fiscal_position`` (``:12-18``)
     - portado
     - consulta ``account.fiscal.position``, que **sí** existe aquí

Por qué NO está bloqueado
==========================

El comentario de la fuente lo llama *"Caching technical field"*: es un
computado sin ``store`` cuyo único trabajo es evitar repetir la consulta
dentro de un mismo recorrido. Su insumo es ``account.fiscal.position``, y
está portado en este árbol con los tres campos que la consulta necesita:

- ``AccountFiscalPosition.foreign_vat``
  (``addons/account/models/account_fiscal_position.py:96``);
- ``AccountFiscalPosition.country``  (``:75``) — la referencia lo llama
  ``country_id``; aquí el nombre del campo es ``country`` (mismo criterio que
  ``ResPartner.country``);
- ``AccountFiscalPosition.company`` (``:55``), que es lo que hace resoluble
  el ``_check_company_domain`` de la fuente.

*Métrica:* ``grep -c "AccountFiscalPosition" addons/account/models/account_fiscal_position.py``
da hits en la clase y en su ``__init__``; el campo se leyó por número de línea.
*Ciega a:* si la posición fiscal está **poblada** en una base concreta — el
porte responde por el mecanismo, no por los datos.

Divergencias declaradas
========================

1. **``@api.depends_context('company')`` no se porta como decorador.** Aquí la
   empresa activa se lee dentro del cuerpo con
   :func:`orm.environments.get_current_company`, que es el mismo dato por otra
   puerta. El decorador de la fuente sirve a la invalidación de su caché de
   computados; una ``property`` sin ``store`` recalcula siempre, así que no
   hay caché que invalidar.
2. **La consulta va por el ORM, no por ``search`` con dominio.** El
   ``('foreign_vat', '!=', False)`` de la fuente significa «no vacío»: aquí el
   campo es ``Char(blank=True, default='')``, así que el predicado equivalente
   excluye la cadena vacía y el ``NULL``. Misma población, otro dialecto.
3. **``limit=1`` → ``.exists()``.** La fuente pide una fila y la evalúa como
   booleano; ``.exists()`` es lo mismo sin traerla.
"""
from django.apps import apps

from orm.environments import get_current_company
from orm.model_classes import extend_model


def _has_foreign_fiscal_position(country):
    """≙ ``_compute_has_foreign_fiscal_position`` (``odoo19c: :12-18``).

    ¿Hay alguna posición fiscal de la empresa activa que declare un
    identificador fiscal propio (``foreign_vat``) en **este** país?
    """
    fiscal_position = apps.get_model('account', 'AccountFiscalPosition')
    queryset = (fiscal_position.objects
                .filter(country=country)
                .exclude(foreign_vat='')
                .exclude(foreign_vat=None))
    predicate = fiscal_position._check_company_domain(get_current_company())
    if predicate is not None:
        queryset = queryset.filter(predicate)
    return queryset.exists()


def apply_base_vat_res_country_extensions():
    """Cuelga sobre ``res.country`` lo que ``base_vat`` le añade — ≙ ``_inherit``."""
    extend_model('base', 'ResCountry', propiedades={
        'has_foreign_fiscal_position': _has_foreign_fiscal_position,
    })
