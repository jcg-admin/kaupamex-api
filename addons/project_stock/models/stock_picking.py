"""``stock.picking`` — la FK al proyecto (Odoo ``project_stock``).

Adaptación de Odoo ``project_stock/models/stock_picking.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 9 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST en la fuente: 1 clase (``_inherit = 'stock.picking'``),
**1 campo** (``project_id``, línea 9), 0 métodos.

Porte — 1 de 1 símbolos
=========================

- ``project_id`` (:9) — **portado** como ``project`` (FK a
  ``project.Project``): la convención local de ``stock.StockPicking`` nombra
  las FK sin el sufijo ``_id`` (``sale_order``, ``picking_type``,
  ``partner``); Django genera la columna ``project_id`` igualmente. El
  fragmento ``domain=[('is_template', '=', False)]`` de la referencia queda
  BLOQUEADO por ``project.Project.is_template`` — el campo no está portado
  (medido: 0 hits en ``addons/project`` y ``addons/hr_timesheet``, misma
  ausencia que ``hr_timesheet/models/project_project.py`` ya declaró para
  ``_toggle_template_mode``); su análogo Django sería
  ``limit_choices_to={'is_template': False}`` sobre esta misma FK. Sucesor:
  tarea PENDIENTE DE ASIGNAR (resumen de este pase).

La migración de la columna va en la app DUEÑA del modelo
(``addons/stock/migrations/``) — wiring del orquestador, mismo criterio que
las columnas que ``hr_timesheet`` cuelga sobre ``analytic``/``project``.
"""
import fields
import models

from orm.model_classes import extend_model


def apply_project_stock_stock_picking_extensions():
    """Cuelga la FK ``project`` sobre ``stock.picking`` — ≙
    ``_inherit = 'stock.picking'``. La llama ``ProjectStockConfig.ready()``.

    Nombre punteado porque el destino declara ``_name = 'stock.picking'``
    (``addons/stock/models/stock_picking.py``). ``related_name='pickings'``
    da el reverso ``Project.pickings`` que consume
    ``models/project_project.py`` de este mismo addon.
    """
    extend_model('stock.picking', campos={
        'project': fields.Many2one(
            'project.Project', on_delete=models.SET_NULL, null=True,
            blank=True, related_name='pickings', db_index=True,
            help_text='Odoo project_id (project_stock). Proyecto al que '
                      'pertenece el albarán. El domain de la referencia '
                      '(is_template=False) queda pendiente — ver docstring '
                      'del módulo.',
        ),
    })


__all__ = ['apply_project_stock_stock_picking_extensions']
