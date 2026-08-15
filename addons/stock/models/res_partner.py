r"""Lo que ``stock`` le cuelga al contacto — ≙ ``_inherit = 'res.partner'``.

Adaptación de Odoo ``stock/models/res_partner.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3, 25 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

Qué es: las **dos ubicaciones por defecto de un contacto**. Cuando se le envía
mercancía, ``property_stock_customer`` es el destino; cuando se recibe de él,
``property_stock_supplier`` es el origen. Sin ellas un movimiento hacia un
contacto no sabe por dónde sale ni por dónde entra.

Por qué entra ahora, y no es alcance inventado
================================================

``stock_warehouse.py:736`` ya escribe los dos campos:

.. code-block:: python

   partner_model.objects.filter(pk=…).update(
       property_stock_customer=transito, property_stock_supplier=transito)

y **ninguno existía** — medido antes de este pase:
``grep -rn property_stock src/addons/base/models/res_partner.py`` → **0**. Ese
``update`` habría reventado con ``FieldError`` en la primera creación de
almacén con contacto. El propio docstring de ``stock_warehouse.py:131`` lo
listaba como símbolo que falta y que ese archivo espera. Ver :ref:`h-api-615`.

Porte símbolo por símbolo — 4 de 4
====================================

Medido por AST sobre el cuerpo de ``class ResPartner`` de la referencia: **5**
entradas, de las que ``_inherit`` no es un símbolo a portar (aquí se expresa
colgando de ``addons.base.models.ResPartner``). Quedan 4.

.. list-table::
   :header-rows: 1
   :widths: 32 12 56

   * - Símbolo (línea)
     - Estado
     - Forma aquí
   * - ``_check_company_auto`` (``:9``)
     - portado
     - atributo de clase verbatim sobre ``ResPartner``
   * - ``property_stock_customer`` (``:11-14``)
     - portado
     - ``fields.Many2one`` a ``stock.StockLocation``
   * - ``property_stock_supplier`` (``:15-18``)
     - portado
     - ``fields.Many2one`` a ``stock.StockLocation``
   * - ``picking_warn_msg`` (``:19``)
     - portado
     - ``fields.Text``
   * - ``action_view_stock_serial`` (``:21-25``)
     - portado
     - devuelve el descriptor de acción; el ``_for_xml_id`` se resuelve por
       ``ir.model.data`` cuando la acción esté sembrada, con el mismo
       ``domain``/``context`` de la fuente

*Métrica:* entradas del cuerpo de ``class ResPartner``, contadas por AST sobre
el archivo de la referencia.
*Ciega a:* lo que otros addons cuelgan de ``res.partner`` — este conteo sólo ve
el archivo de ``stock``.

Divergencia declarada — ``company_dependent``
===============================================

La referencia marca los dos campos ``company_dependent=True``: su valor se
guarda por empresa en ``ir.property`` (en 19, ``ir.default``), no en una columna
de ``res_partner``. Aquí son **columnas normales**, porque el mecanismo de campo
dependiente de empresa **no está construido** en este árbol — medido:
``grep -rn "company_dependent" src/ addons/`` → 0 antes de este archivo.

No se rodea con un valor inventado: la columna guarda **un** valor, que es el de
la empresa activa cuando se escribió. Es una divergencia de mecanismo declarada
(``porte-completo-no-parcial.md``, desenlace 1), y su cierre es la tarea
**#381** — construir el campo dependiente de empresa sobre ``ir.default``, que
sí está portado (``src/addons/base/models/ir_default.py:145``).
"""
import fields
import models

from addons.base.models import ResPartner


def _add_if_absent(model, name, field):
    """Cuelga el campo sólo si el modelo no lo tiene ya.

    Idempotente a propósito: ``ready()`` puede correr más de una vez en un
    proceso (recarga del autoreloader), y ``add_to_class`` sobre un campo que ya
    existe rompe con ``FieldError``. Mismo criterio que
    ``sale/models/res_company.py::_add_if_absent``.
    """
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def action_view_stock_serial(self):
    """≙ ``action_view_stock_serial`` (``odoo19c: stock/models/res_partner.py:21-25``).

    Los números de serie que pasaron por este contacto o por cualquiera de sus
    hijos. El ``child_of`` de la fuente se expresa con la ruta materializada del
    contacto, igual que ``StockLocation`` lo hace con ``parent_path``.
    """
    return {
        'type': 'ir.actions.act_window',
        'xml_id': 'stock.action_production_lot_form',
        'res_model': 'stock.lot',
        'domain': [('partner_ids', 'child_of', [self.pk])],
        'context': {'display_complete': True},
    }


def apply_stock_res_partner_extensions():
    """≙ ``_inherit = 'res.partner'`` de ``stock``.

    Se llama desde ``StockConfig.ready()``, no al importar: en tiempo de import
    el registro de modelos aún no está poblado.
    """
    # ≙ ``_check_company_auto = True`` (``odoo19c: :9``) — el interruptor que
    # activa la verificación de coherencia de empresa sobre los campos marcados
    # ``check_company=True``, que aquí son los dos ``property_stock_*``.
    if not hasattr(ResPartner, '_check_company_auto'):
        ResPartner._check_company_auto = True

    _add_if_absent(ResPartner, 'property_stock_customer', fields.Many2one(
        'stock.StockLocation', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='partners_as_customer_location',
        verbose_name='Ubicación de cliente',
        help_text='Ubicación destino al enviarle mercancía a este contacto '
                  '(Odoo property_stock_customer).',
    ))
    _add_if_absent(ResPartner, 'property_stock_supplier', fields.Many2one(
        'stock.StockLocation', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='partners_as_supplier_location',
        verbose_name='Ubicación de proveedor',
        help_text='Ubicación origen al recibir mercancía de este contacto '
                  '(Odoo property_stock_supplier).',
    ))
    _add_if_absent(ResPartner, 'picking_warn_msg', fields.Text(
        blank=True, default='', verbose_name='Aviso en la transferencia',
        help_text='Mensaje que se muestra al operar una transferencia con este '
                  'contacto (Odoo picking_warn_msg).',
    ))

    if not hasattr(ResPartner, 'action_view_stock_serial'):
        ResPartner.action_view_stock_serial = action_view_stock_serial
