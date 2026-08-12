r"""Lo que ``sale`` le cuelga a la empresa — ≙ ``_inherit`` (tarea #256).

Adaptación de ``addons/sale/models/res_company.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, 64 líneas).

*Métrica:* entradas del cuerpo de ``class ResCompany``, contadas por AST.
Son **11** con ``_inherit``; **10** sin él, que es el denominador que aplica
(``_inherit`` no es un símbolo a portar: aquí se expresa colgando de
``addons.base.models.ResCompany``).
*Ciega a:* lo que la referencia declara para ``res.company`` fuera de este
archivo — otros addons le cuelgan lo suyo, y este conteo no los ve.

**Se portan 2 de 10** — ``quotation_validity_days`` (campo) y
``_check_quotation_validity_days`` (constraint). Los otros **8** quedan fuera,
agrupados en 5 ejes; ninguno es una omisión silenciosa:

1. **``portal_confirmation_sign``/``portal_confirmation_pay``**
   (``odoo19c: res_company.py:16-17``) — toggles del flujo de firma/pago en
   el portal de cliente. Sin portal en este stack (DEC-FW-01: API + UI propia,
   no vistas XML de Odoo), no hay superficie que los lea.
2. **``prepayment_percent`` + ``downpayment_account_id`` +
   ``_check_prepayment_percent``** (``:18-21,50-58,60-64``) — el eje de anticipo
   parcial de la cotización (factura de downpayment antes de confirmar). No
   existe todavía ningún flujo de downpayment portado que lo consuma.
3. **``sale_discount_product_id``** (``:28-37``) — producto usado para
   materializar un descuento como línea de factura. Depende de
   ``account.chart.template`` (tarea #140, Bloque 1), no cerrado aún.
4. **``sale_onboarding_payment_method``** (``:40-48``) — selección del wizard
   de onboarding de Odoo (elegir método de pago la primera vez que se usa
   Ventas). Sin wizard de onboarding en este stack.
5. **``_check_company_auto = True``** (``odoo19c: res_company.py:9``) — es el
   interruptor que activa la verificación automática de coherencia de empresa
   sobre los campos marcados ``check_company=True``. Medido en el archivo: el
   único campo que lleva esa marca es ``sale_discount_product_id``
   (``:36``), que ya queda fuera por el eje 3. Sale **con** ese eje: encender
   el interruptor sin el campo que vigila no protegería nada. Vuelve cuando
   vuelva el eje 3.

Por qué ``quotation_validity_days`` sí, ahora
===============================================

Es el insumo de ``SaleOrder._compute_validity_date`` (tarea #256, mismo pase):
sin el campo en la empresa, el cómputo de vigencia de la cotización no tiene
de dónde leer el plazo. Se porta solo, sin arrastrar los otros 8 — el mismo
criterio que ``account/models/res_company.py`` aplicó al Bloque 1: portar lo
que una cadena medida necesita, no el bloque entero por comodidad de orden.
"""
# NOTA — ``violation_error_message`` es su PRIMER uso en este árbol
# (``grep -rn violation_error_message src/`` -> 0 hits antes de este archivo).
# Se usa porque la constraint de la referencia lleva dos argumentos: el
# predicado y el mensaje. Portar sólo el predicado deja al usuario con el
# error crudo de PostgreSQL en vez del texto que la referencia escribió, que
# es media constraint (``porte-completo-no-parcial.md``). Que el resto del
# árbol no lo use todavía es deuda propia, no razón para repetirla aquí.
from django.db import models as dj_models
from django.db.models import Q

import fields
from tools.translate import _

from addons.base.models import ResCompany


def _add_if_absent(model, name, field):
    """Cuelga el campo sólo si el modelo no lo tiene ya.

    Idempotente a propósito: ``ready()`` puede correr más de una vez en un
    proceso (recarga del autoreloader), y ``add_to_class`` sobre un campo que
    ya existe rompe con ``FieldError``. Duplicado de
    ``account/models/res_company.py::_add_if_absent`` — mismo criterio, otro
    módulo (los dos cuelgan de un ``ResCompany`` que no es suyo).
    """
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def _add_check_constraint_if_absent(model, name, constraint):
    """Cuelga un ``CheckConstraint`` en ``model._meta.constraints`` si no
    existe ya uno con ese ``name``.

    ``_meta.constraints`` es una lista mutable normal de ``Options``
    (``django/db/models/options.py``, ``self.constraints = []`` en
    ``__init__``) que ``validate_constraints``/``full_clean`` recorren en
    vivo — no hace falta declarar la constraint en el cuerpo de la clase para
    que se valide. Mismo criterio idempotente que ``_add_if_absent``: sin el
    guard, una recarga del autoreloader duplicaría la entrada.
    """
    if not any(c.name == name for c in model._meta.constraints):
        model._meta.constraints.append(constraint)


def apply_sale_extensions():
    """≙ ``_inherit = 'res.company'`` de ``sale`` (``odoo19c: res_company.py``).

    Se llama desde ``SaleConfig.ready()``, no al importar: en tiempo de
    import el registro de modelos aún no está poblado.
    """
    _add_if_absent(ResCompany, 'quotation_validity_days', fields.Integer(
        default=30,
        help_text='Días entre la cotización y su vencimiento; 0 desactiva '
                  'el vencimiento automático (Odoo quotation_validity_days, '
                  'res_company.py:22-27).',
    ))
    _add_check_constraint_if_absent(
        ResCompany, 'sale_quotation_validity_days_check',
        dj_models.CheckConstraint(
            condition=Q(quotation_validity_days__gte=0),
            name='sale_quotation_validity_days_check',
            violation_error_message=_(
                'No puede fijar un número negativo para la validez por '
                'defecto de la cotización. Déjelo vacío (o en 0) para '
                'desactivar el vencimiento automático de cotizaciones.'
            ),
        ),
    )
