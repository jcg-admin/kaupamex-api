"""Lo que ``account`` le cuelga a la empresa — ≙ ``_inherit`` (tarea #140).

Adaptación de ``addons/account/models/company.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``). **Sólo dos de los 72 campos del Bloque 1**, y la razón de portar
exactamente esos dos —y no el bloque entero— es que son los que desbloquean una
cadena medida, no una preferencia de orden.

Por qué estos dos ahora
========================

:ref:`h-api-340` midió que la línea de venta extrae el IVA de un parámetro
global en vez de los impuestos del producto. La primera mitad de su sucesora
(#141) ya está: ``compute_all`` existe. La segunda mitad —reapuntar
``SaleOrderLine.price_tax``— tropieza con algo que no es código:

*Métrica:* migraciones que crean filas en ``account_tax``.
*Ciega a:* filas creadas por fixture o comando en un despliegue concreto.
Medido: ``grep -rln "AccountTax" src/addons/*/migrations/*.py`` da dos
archivos, **ambos de esquema** (``0001_initial``, ``0003_…``). **Nadie siembra
un impuesto.** [PROVEN]

Reapuntar ``price_tax`` sobre esa base daría impuesto **0** en toda línea —
un cambio que se ve verde en los tests y borra el IVA en producción. El
eslabón que falta no es el motor: es de dónde sale el impuesto por defecto
cuando un producto no declara el suyo.

La referencia lo responde en dos líneas: la empresa lleva su impuesto de venta
por defecto (``odoo19c: company.py:126-127``) y el producto lo usa como
``default`` de su M2M (``odoo19c: product.py:44``). Con eso, un producto nuevo
nace con el impuesto de su empresa y el eje funciona.

Lo que NO hace falta para esto — y por qué importa decirlo
===========================================================

``account.chart.template`` **puebla** ese campo al instalar un plan contable
(``odoo19c: chart_template.py:731-743``), y son 1537 líneas orientadas a cargar
un plan completo desde CSV. Es trabajo real y sigue pendiente (#140, otra
mitad), pero **no es requisito** de esta cadena: la referencia declara el campo
en ``res.company``, no en el chart, precisamente para que una empresa pueda
fijar su impuesto por defecto sin instalar un plan entero.

Portar el chart primero habría sido el orden intuitivo y el equivocado.

Divergencias declaradas
========================

- **``check_company=True``** no tiene análogo: es una validación del ORM de la
  referencia que comprueba que el registro apuntado pertenece a la misma
  empresa. Aquí se cubre con un ``limit_choices_to`` — que restringe en el
  formulario y en la validación del serializer, **pero no en la base**. Un
  ``AccountTax`` de otra empresa asignado por código pasaría. Es el mismo hueco
  que el resto de los ``check_company`` del porte, y su cierre es el mecanismo
  de row-scoping L1 (tarea #133, :ref:`h-api-259`), no un parche por campo.
- **``account_purchase_receipt_fiscal_position_id``** y los otros 70 del Bloque
  1 siguen fuera: los cierra la tarea **#137** (mapeo campo por campo), que a su
  vez espera la decisión del eje partner (#142).
"""
from django.db import models as dj_models

import fields

from addons.account.models.chart_template import ChartTemplate
from addons.base.models import ResCompany


def _default_tax(help_text, tax_use):
    """FK al impuesto por defecto de la empresa.

    ``on_delete=PROTECT`` y no ``SET_NULL``: borrar un impuesto que es el
    default de una empresa deja productos nuevos sin impuesto de forma
    silenciosa. La referencia usa el default de Odoo (``restrict``) por la
    misma razón.
    """
    return fields.Many2one(
        'account.AccountTax',
        null=True, blank=True, on_delete=dj_models.PROTECT,
        related_name='+', limit_choices_to={'type_tax_use': tax_use},
        help_text=help_text,
    )


def _add_if_absent(model, name, field):
    """Cuelga el campo sólo si el modelo no lo tiene ya.

    Idempotente a propósito: ``ready()`` puede correr más de una vez en un
    proceso (recarga del autoreloader), y ``add_to_class`` sobre un campo que
    ya existe rompe con ``FieldError``.
    """
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def apply_account_extensions():
    """≙ ``_inherit = 'res.company'`` de ``account`` (``odoo19c: company.py``).

    Se llama desde ``AccountConfig.ready()``, no al importar: en tiempo de
    import el registro de modelos aún no está poblado.
    """
    _add_if_absent(ResCompany, 'account_sale_tax', _default_tax(
        'Impuesto de venta por defecto de la empresa. Lo hereda todo producto '
        'nuevo que no declare el suyo (Odoo account_sale_tax_id, '
        'company.py:126).',
        'sale',
    ))
    _add_if_absent(ResCompany, 'account_purchase_tax', _default_tax(
        'Impuesto de compra por defecto de la empresa (Odoo '
        'account_purchase_tax_id, company.py:127).',
        'purchase',
    ))
    _add_if_absent(ResCompany, 'chart_template', fields.Char(
        max_length=64, null=True, blank=True,
        help_text='Código del plan contable cargado en esta empresa (Odoo '
                  'chart_template, company.py:117). Una empresa hija hereda '
                  'el de su raíz al crearse.',
    ))
    dj_models.signals.post_save.connect(
        load_chart_for_new_company, sender=ResCompany,
        dispatch_uid='account.load_chart_for_new_company',
    )


def load_chart_for_new_company(sender, instance, created, **kwargs):
    """Carga el plan de la raíz en la empresa recién creada.

    ≙ el ``create`` de ``odoo19c: account/models/company.py:486-498``: si la
    raíz de su jerarquía declara un plan, la nueva empresa lo instancia.

    **Por qué se lee el padre y no ``instance.parent_ids``.** La referencia usa
    ``parent_ids[0]`` y difiere la carga a ``cr.precommit`` — no por capricho:
    ese cálculo necesita el estado del registro ya asentado. Aquí ocurre lo
    mismo por otra vía: ``ResCompany.save()`` calcula ``parent_path`` **después**
    del ``INSERT`` (``res_company.py:581-586``), así que en el instante del
    ``post_save`` la ruta materializada todavía está vacía y ``parent_ids``
    devuelve sólo la propia empresa. Leer ``instance.parent`` —una FK, escrita
    ya— y pedirle a él su raíz evita depender de un valor que aún no existe.

    Una empresa **raíz** (``parent is None``) no entra por aquí, igual que en la
    referencia: su plan lo elige quien la aprovisiona (allá,
    ``res_config_settings.py:223``). Esa mitad es la tarea #156.

    ``dispatch_uid`` porque ``ready()`` puede correr dos veces con el
    autoreloader, y sin él el receptor se conectaría por duplicado.
    """
    if not created or instance.parent is None:
        return
    codigo = getattr(instance.parent.root_id, 'chart_template', None)
    if codigo:
        ChartTemplate.try_loading(codigo, instance)
