"""``project.project`` — los albaranes del proyecto (Odoo ``project_stock``).

Adaptación de Odoo ``project_stock/models/project_project.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 45 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST en la fuente: 1 clase (``_inherit = 'project.project'``),
0 campos, **4 métodos** — los cuatro arman un ``ir.actions.act_window``.

Porte símbolo por símbolo — 4 símbolos: navegación no portada, capacidad portada
==================================================================================

Los cuatro métodos son navegación del cliente web: construyen el diccionario
de acción (``view_mode``, ``context`` con defaults de formulario, ``help``
renderizado por QWeb vía ``ir.ui.view._render_template``). Mismo criterio que
``account_debit_note/models/account_move.py`` (*"navegación pura … sin
lógica de negocio propia"*) y ``hr/models/res_partner.py`` (familia (b)): la
acción NO se porta; la CAPACIDAD que exponía —filtrar los albaranes del
proyecto por tipo de operación— SÍ, como ``pickings_of_type``.

.. list-table::
   :header-rows: 1

   * - Símbolo de la referencia (línea)
     - Desenlace
   * - ``action_open_deliveries`` (:10-12)
     - navegación no portada; capacidad ≙ ``pickings_of_type('outgoing')``.
   * - ``action_open_receipts`` (:14-16)
     - navegación no portada; capacidad ≙ ``pickings_of_type('incoming')``.
   * - ``action_open_all_pickings`` (:18-20)
     - navegación no portada; capacidad ≙ ``pickings_of_type()``.
   * - ``_get_picking_action`` (:22-45)
     - navegación no portada; su dominio —``project_id = self.id`` más
       ``picking_type_id.code = <tipo>``— es el cuerpo de
       ``pickings_of_type``. Lo demás del método es UI: ``view_mode``,
       ``default_partner_id``/``default_project_id`` (defaults de
       formulario del cliente) y el ``help`` de
       ``stock.help_message_template``, cuyo análogo local sin QWeb ya
       existe (``stock.StockPicking.get_empty_list_help``).

``self.ensure_one()`` de la referencia no aplica: Django no tiene recordsets
— una instancia ES un registro (mismo criterio que ``certificate/models/
certificate.py``).
"""
from orm.model_classes import extend_model


def pickings_of_type(self, picking_type_code=None):
    """Los albaranes del proyecto, opcionalmente por tipo de operación —
    la capacidad de ``_get_picking_action`` y sus tres envoltorios
    (``odoo19c: project_stock/models/project_project.py:10-45``) sin la
    navegación (ver docstring del módulo).

    ``picking_type_code``: ``'outgoing'`` (entregas, ≙
    ``action_open_deliveries``), ``'incoming'`` (recepciones, ≙
    ``action_open_receipts``), ``'internal'``, o ``None`` para todos
    (≙ ``action_open_all_pickings``).

    ``self.pickings`` es el reverso de la FK que este mismo addon cuelga
    sobre ``stock.picking`` (``models/stock_picking.py``).
    """
    pickings = self.pickings.all()
    if picking_type_code:
        pickings = pickings.filter(picking_type__code=picking_type_code)
    return pickings


def apply_project_stock_project_project_extensions():
    """Cuelga la capacidad de filtrado sobre ``project.Project`` — ≙
    ``_inherit = 'project.project'``. La llama
    ``ProjectStockConfig.ready()``.

    Par de Django (``'project', 'Project'``) porque el destino no declara
    ``_name`` (``addons/project/models/project_project.py``).
    """
    extend_model('project', 'Project', metodos={
        'pickings_of_type': pickings_of_type,
    })


__all__ = ['apply_project_stock_project_project_extensions']
