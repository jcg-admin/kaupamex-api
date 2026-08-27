r"""``ir.actions.report`` extendido por ``account`` — un campo portado, cuatro bloqueados.

Adaptación de ``addons/account/models/ir_actions_report.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 96 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 2 de 6
=====================================

.. list-table::
   :header-rows: 1
   :widths: 40 15 45

   * - Símbolo
     - Estado
     - Nota
   * - ``is_invoice_report``
     - **portado**
     - campo booleano plano, sin dependencia
   * - ``_unlink_except_master_tags``
     - **portado** (adaptado)
     - guard de integridad; se resuelve por ``ir.model.data`` en vez de
       ``env.ref``, mismo patrón que ``res_users.py`` de este pase
   * - ``_render_qweb_pdf_prepare_streams``
     - **bloqueado**
     - motor QWeb ausente (ver abajo)
   * - ``_is_invoice_report``
     - **bloqueado**
     - depende de ``self._get_report(report_ref)``, ausente
   * - ``_get_splitted_report``
     - **bloqueado**
     - QWeb (``_prepare_html``) + el mismo ``content`` que arma el método
       bloqueado de arriba
   * - ``_pre_render_qweb_pdf``
     - **bloqueado**
     - motor QWeb ausente (el propio nombre lo declara)
   * - ``_get_rendering_context``
     - **bloqueado**
     - motor QWeb ausente — mismo bloqueo que ``stock/models/
       ir_actions_report.py`` ya documenta en este árbol

Bloqueo estructural — el motor es libharu, no QWeb (ADR-017)
=================================================================

Cuatro de los seis símbolos manipulan el pipeline de render **QWeb** de la
referencia: ``_get_rendering_context``, ``_pre_render_qweb_pdf``,
``_render_qweb_pdf_prepare_streams``, ``_get_splitted_report``. Medido en
este mismo pase: ``grep -n "def _get_rendering_context\|def
_pre_render_qweb_pdf\|def _render_qweb_pdf_prepare_streams\|def
_get_splitted_report" src/addons/base/models/ir_actions_report.py`` → **0
hits, los cuatro** [PROVEN]. Nuestro ``IrActionsReport``
(``src/addons/base/models/ir_actions_report.py:305``) declara otra
superficie —``render``, ``_render_pdf``, ``_descriptor_from_view``— sobre el
motor PDF propio (ADR-017, libharu). Es el mismo bloqueo que
``stock/models/ir_actions_report.py`` ya registró para su único símbolo;
aquí son cuatro, con la misma causa raíz y el mismo desenlace: **(a)
divergencia de mecanismo**, sin sucesor propio — el sucesor es el que ya
existe para el motor QWeb en general (mencionado en el docstring de
``stock``).

``_is_invoice_report`` cae con ellos por transitividad: llama a
``self._get_report(report_ref)``, que tampoco existe (el análogo más cercano
es ``get_report_from_name``, otra firma — no es el mismo símbolo).

Lo que SÍ se porta
=====================

**``is_invoice_report``** no depende de nada del motor de render: es un
booleano plano que marca qué reportes son de factura. Se porta sin ajuste.

**``_unlink_except_master_tags``** es un guard de integridad —*"no borres
estos reportes maestros, el motor de generación de PDF de facturación los
usa"*— independiente del motor de render. Depende sólo de resolver 7
identificadores externos a filas de ``ir.actions.report``, y ese mecanismo
**sí** existe (``ir.model.data``, el patrón ya establecido por
``res_company.py`` y ``res_users.py`` de este mismo pase).

Corrección de un defecto tipográfico de la fuente, con su cita
====================================================================

La lista de la referencia (``odoo19c: ir_actions_report.py:80-87``) tiene un
bug: faltan comillas/coma entre dos elementos, así que Python los concatena
en tiempo de compilación:

.. code-block:: python

    master_xmlids = [
        "account_invoices",
        "action_account_original_vendor_bill"
        "account_invoices_without_payment",   # <- concatenados por Python
        "action_report_journal",
        ...
    ]

El resultado real de la referencia es una lista de **6** cadenas (una de
ellas la concatenación accidental de dos identificadores que nunca
resolverá), no 7. Se porta la lista **corregida** —7 identificadores
separados— porque propagar el defecto silenciosamente sería peor que
señalarlo: ninguno de los 7 está sembrado en este árbol de todos modos
(medido: ``grep -rln "action_report_journal\|account_invoices"
src/addons/base/data/*.py`` → 0 hits [PROVEN]), así que el guard queda
inerte hasta que existan esos datos — corregido o no, el comportamiento
observable hoy es idéntico.
"""
import fields

from addons.base.models.ir_actions_report import IrActionsReport
from addons.base.models.ir_model import IrModelData
from exceptions import UserError
from tools.translate import _

#: Los 7 reportes maestros que el guard protege — ≙ ``master_xmlids``
#: (``odoo19c: account/models/ir_actions_report.py:80-87``), con el defecto
#: tipográfico de la fuente corregido (ver docstring del módulo). Todos con
#: ``module='account'``.
_MASTER_REPORT_XMLIDS = (
    'account_invoices',
    'action_account_original_vendor_bill',
    'account_invoices_without_payment',
    'action_report_journal',
    'action_report_payment_receipt',
    'action_report_account_statement',
    'action_report_account_hash_integrity',
)


def _except_master_tags(self):
    """≙ ``_unlink_except_master_tags``
    (``odoo19c: account/models/ir_actions_report.py:78-89``).

    Impide borrar cualquiera de los 7 reportes maestros que el motor de
    generación de PDF de facturación referencia por nombre.
    """
    xmlids_in_use = set(
        IrModelData.objects
        .filter(module='account', name__in=_MASTER_REPORT_XMLIDS,
                res_id=self.pk)
        .values_list('name', flat=True),
    )
    if xmlids_in_use:
        raise UserError(_(
            'No se puede eliminar este reporte (%(nombre)s): lo usa el '
            'motor de generación de PDF de facturación.',
        ) % {'nombre': self.name})


def apply_account_extensions():
    """≙ ``_inherit = 'ir.actions.report'`` de ``account``.

    Cuelga sólo los dos símbolos portables — ver el docstring del módulo
    para los cuatro bloqueados por el motor QWeb ausente.
    """
    if not hasattr(IrActionsReport, 'is_invoice_report'):
        IrActionsReport.add_to_class('is_invoice_report', fields.Boolean(
            default=False, verbose_name='Reporte de factura',
            help_text='Odoo is_invoice_report — marca los reportes propios '
                      'de facturación.',
        ))
    if not hasattr(IrActionsReport, '_except_master_tags'):
        IrActionsReport._except_master_tags = _except_master_tags
