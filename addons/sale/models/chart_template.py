"""Lo que ``sale`` le cuelga al cargador del plan contable — ≙ ``_inherit``.

Adaptación de Odoo ``addons/sale/models/chart_template.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3 — mecanismo: copia + adaptación
con atribución; 10 líneas, 1 ``def``: medido por AST —
``AccountChartTemplate._get_property_accounts``).

El archivo entero de la fuente es un ``_inherit = 'account.chart.template'``
con un solo método, que llama a ``super()`` y añade una entrada al mapa:
``property_accounts['downpayment_account_id'] = 'res.company'``. Dice quién es
dueño de la cuenta de anticipo — la empresa — para que ``_post_load_data``
siembre su ``ir.default`` al cargar el plan.

Mecanismo de la extensión
==========================

Aquí el cargador (``account.models.chart_template.ChartTemplate``) es una clase
de métodos de clase, no un ``AbstractModel``, así que un addon no lo extiende
con ``_inherit``. El equivalente ya existía en ese mismo archivo para el otro
método extensible: un registro de funciones más su decorador. Se reusa el
mismo, ahora para las cuentas de propiedad: ``@property_accounts_override``.

Medido sobre ``odoo19c`` antes de construirlo: ``sale`` es el **único** addon
del árbol que sobreescribe ``_get_property_accounts`` — los otros dos aciertos
del grep son la declaración y su llamador, ambos en ``account``.

Divergencia de nombre declarada
================================

La fuente escribe la clave ``'downpayment_account_id'`` porque así se llama el
campo en su ``res.company``. Aquí el campo es ``downpayment_account`` —
**forma A** de ADR-029, congelada en ``scripts/fk_naming_baseline.txt`` (#143)
y por tanto no renombrable en este pase. El mapa lleva el nombre **del campo
real**, que es lo que su consumidor busca en ``_meta``; escribir el de la
fuente haría que la guarda lo descartara en silencio y la entrada no sembraría
nada, que es la forma de :ref:`h-api-346`.
"""
from addons.account.models.chart_template import property_accounts_override


@property_accounts_override
def add_downpayment_account(chart_template_cls, property_accounts):
    """La cuenta de anticipo pertenece a la empresa — ≙ ``:7-10``.

    ``chart_template_cls`` es la clase del cargador, ≙ el ``self`` del
    ``AbstractModel`` de la fuente: llega por si un ajuste necesita consultarla,
    igual que los ajustes de ``ACCOUNTS_DATA_OVERRIDES``.
    """
    property_accounts['downpayment_account'] = 'res.company'
    return property_accounts
