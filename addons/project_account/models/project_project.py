"""``project.project`` — secciones contables del panel de rentabilidad.

Adaptación de Odoo ``project_account/models/project_project.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 183 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST en la fuente: 1 clase (``_inherit = 'project.project'``),
0 campos, **10 métodos**. Desenlace por símbolo: 2 portados, 5 con arista de
bloqueo, 3 de navegación pura (no se portan — mismo criterio que
``account_debit_note/models/account_move.py``: *"navegación pura del cliente
web de Odoo, sin lógica de negocio propia"*).

Porte símbolo por símbolo — 10 símbolos: 2 portados, 5 bloqueados, 3 navegación
=================================================================================

.. list-table::
   :header-rows: 1

   * - Símbolo de la referencia (línea)
     - Desenlace
   * - ``_get_profitability_labels`` (:77-83)
     - **portado** — encadenado con fusión de dict (ver divergencia 1).
   * - ``_get_profitability_sequence_per_invoice_type`` (:85-91)
     - **portado** — ídem.
   * - ``_add_purchase_items`` (:14-20)
     - BLOQUEADO por ``project.Project.account_id`` — orquesta
       ``_get_costs_items_from_purchase`` sobre la cuenta analítica del
       proyecto (``odoo19c: project/models/project_project.py:98``), no
       portada; su hogar es ``addons/project``, fuera del write-set de este
       pase. Además filtra por ``self.env.user.has_group`` (usuario
       ambiental, sin análogo de sesión en el modelo). Sucesor: tarea
       PENDIENTE DE ASIGNAR (resumen de este pase).
   * - ``_get_add_purchase_items_domain`` (:22-29)
     - BLOQUEADO por ``project.Project._get_already_included_profitability_invoice_line_ids``
       — método de la infraestructura de rentabilidad del addon base
       ``project`` (``odoo19c: project/models/project_project.py:1036``), no
       portado; hogar ``addons/project``, fuera del write-set. Sucesor:
       tarea PENDIENTE DE ASIGNAR (resumen de este pase).
   * - ``_get_costs_items_from_purchase`` (:31-68)
     - BLOQUEADO por ``account.AccountMoveLine.analytic_distribution`` — el
       ``AnalyticMixin`` (``addons/analytic/models/analytic_mixin.py``) no
       está aplicado a la línea de asiento en este árbol (medido: 0 hits de
       ``analytic_distribution`` en ``account/models/account_move_line.py``);
       hogar ``addons/account``, fuera del write-set. Segundo bloqueador de
       la misma arista raíz: ``Project.account_id``; y la conversión
       multi-moneda (``res.currency._convert``) tampoco existe (misma
       divergencia que ``hr_timesheet`` ya declaró). Sucesor: tarea
       PENDIENTE DE ASIGNAR (resumen de este pase).
   * - ``_get_action_for_profitability_section`` (:70-75)
     - no portado — navegación pura: arma el payload JSON de un botón del
       cliente web (``{'name': 'action_profitability_items', 'type':
       'object', ...}``). Sin consumidor DRF; se porta cuando exista el
       endpoint que lo sirva.
   * - ``action_profitability_items`` (:93-120)
     - no portado — navegación pura: resuelve xmlids de acciones y vistas
       pivot/graph del cliente web (``_for_xml_id`` /
       ``_xmlid_to_res_id``), capa que este árbol no tiene (mismo criterio
       que ``hr/models/res_partner.py`` para ``action_open_employees``).
   * - ``_get_domain_aal_with_no_move_line`` (:122-125)
     - BLOQUEADO por ``project.Project.account_id`` — el dominio es
       ``[('account_id', '=', self.account_id.id), ('move_line_id', '=',
       False)]`` y su primer término es la FK no portada (el conector
       ``AccountAnalyticLine.move_line`` sí existe, ``account/models/
       account_analytic_line.py``). Sucesor: tarea PENDIENTE DE ASIGNAR
       (resumen de este pase).
   * - ``_get_items_from_aal`` (:127-172)
     - BLOQUEADO por ``project.Project.account_id`` — depende del dominio
       anterior. Bloqueadores de segundo orden, medidos: ``res.currency.
       _convert`` (0 hits en el árbol) y los valores ``manufacturing_order``
       / ``picking_entry`` de ``category`` (el ``AccountAnalyticLine`` local
       sólo declara ``other``). Sucesor: tarea PENDIENTE DE ASIGNAR
       (resumen de este pase).
   * - ``action_open_analytic_items`` (:174-183)
     - no portado — navegación pura (``_for_xml_id`` +
       ``literal_eval`` del context de la acción); además depende de
       ``Project.account_id``, la misma arista raíz de arriba.

Divergencias declaradas de los dos símbolos portados
======================================================

1. **``super()`` → ``chain_method`` con fusión de dict.** La referencia
   escribe ``{**super()._get_profitability_labels(), ...}``; este idioma de
   extensión no tiene ``super()``, así que cada hook devuelve SOLO su aporte
   y ``combine=_merge_with_previous`` funde con la implementación previa
   (primero lo que ya había, después lo propio — mismo orden que la
   referencia). Hoy no hay implementación previa: la infraestructura del
   panel del addon base ``project`` (``odoo19c: project/models/
   project_project.py:1030-1036``) no está portada, y ``chain_method``
   instala el hook tal cual — el día que ``addons/project`` la porte, la
   cadena se arma sola porque ``project`` corre antes en ``INSTALLED_APPS``
   (este addon lo declara en ``depends``).
2. **``self.env._()`` → ``tools.translate._``** — el análogo vivo del árbol;
   los textos van en español como el resto de los ports (criterio de
   ``stock.StockPicking.get_empty_list_help``).
"""
from orm.method_chain import chain_method
from orm.model_classes import extend_model
from tools.translate import _


def _merge_with_previous(new, previous):
    """``combine`` para hooks que aportan claves a un dict — ≙
    ``{**super()..., **propio}``. Primero lo que ya había, después lo que
    aporta este addon, como en la referencia."""
    return {**(previous or {}), **(new or {})}


def _get_profitability_labels(self):
    """≙ ``_get_profitability_labels`` (``odoo19c:
    project_account/models/project_project.py:77-83``) — las etiquetas de
    las tres secciones que este addon aporta al panel de rentabilidad.

    Devuelve SOLO el aporte propio; la fusión con la implementación previa
    la hace ``chain_method`` (ver divergencia 1 del módulo).
    """
    return {
        'other_purchase_costs': _('Facturas de proveedor'),
        'other_revenues_aal': _('Otros ingresos'),
        'other_costs_aal': _('Otros costos'),
    }


def _get_profitability_sequence_per_invoice_type(self):
    """≙ ``_get_profitability_sequence_per_invoice_type`` (``odoo19c:
    project_account/models/project_project.py:85-91``) — el orden de las
    tres secciones dentro del panel. Valores verbatim de la fuente."""
    return {
        'other_purchase_costs': 11,
        'other_revenues_aal': 14,
        'other_costs_aal': 15,
    }


def _chain_profitability_hooks(model):
    """Encadena los dos hooks con fusión de dict — el ``luego`` de
    ``extend_model``, porque su bloque ``metodos`` usa el relevo por ``None``
    y aquí la semántica correcta es la combinación."""
    chain_method(
        model, '_get_profitability_labels',
        _get_profitability_labels, combine=_merge_with_previous,
    )
    chain_method(
        model, '_get_profitability_sequence_per_invoice_type',
        _get_profitability_sequence_per_invoice_type,
        combine=_merge_with_previous,
    )


def apply_project_account_project_project_extensions():
    """Cuelga sobre ``project.Project`` el vocabulario contable del panel —
    ≙ ``_inherit = 'project.project'``. La llama
    ``ProjectAccountConfig.ready()``.

    Par de Django (``'project', 'Project'``) porque el destino no declara
    ``_name`` (``addons/project/models/project_project.py``).
    """
    extend_model('project', 'Project', luego=_chain_profitability_hooks)


__all__ = ['apply_project_account_project_project_extensions']
