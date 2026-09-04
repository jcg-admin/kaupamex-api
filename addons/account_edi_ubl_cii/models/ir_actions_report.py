r"""``ir.actions.report`` — lo que ``account_edi_ubl_cii`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/ir_actions_report.py``
(``odoo-tools@622ddc2a``, LGPL-3, 30 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Un símbolo: ``_render_qweb_pdf_prepare_streams``, que embebe el Factur-X en los
PDF de plantilla personalizada.

Por qué este archivo deja de estar bloqueado
=============================================

Hasta el porte del bloque C de ``ir_actions_report`` (tarea #170) este archivo
declaraba **tres** piezas ausentes y no portaba su cuerpo. Dos de las tres
dejaron de faltar; la tercera cambió de sitio. Re-medido en el mismo pase que
lo desbloquea, no heredado de la medición anterior:

.. list-table::
   :header-rows: 1

   * - Pieza que bloqueaba
     - Estado hoy
   * - ``IrActionsReport._render_qweb_pdf_prepare_streams`` no existe (0 hits)
     - **existe** — portado en el bloque C, con la firma de la fuente. Hay
       previa a la que ``wrap_method`` entrega el ``super()``.
   * - ``env['ir.config_parameter'].sudo().get_param`` — el proxy de ``env``
       de este addon no emula ``sudo()``
     - **no hace falta el proxy**: ``SystemParameter.get_param`` es un
       ``classmethod`` que se invoca directo. La elevación de la fuente tampoco
       añade nada aquí — el parámetro no está acotado por fila.
   * - ``env['account.move.send'].with_context(...)`` — ídem con
       ``with_context``, y el método que invoca está bloqueado por ``pypdf``
     - ``context_scope`` es el ``with_context`` de este árbol y
       ``AccountMoveSend`` existe. Lo que **sigue** bloqueado es el propio
       ``_hook_invoice_document_after_pdf_report_render``, y su bloqueo es de
       ``account_edi_ubl_cii/models/account_move_send.py``, no de este archivo.

El tercero es un bloqueo **de otro archivo**, así que aquí el cuerpo se porta
entero y la llamada al enganche queda donde la fuente la tiene. Sólo se alcanza
cuando alguien configura ``account.custom_templates_facturx_list``: con el
parámetro vacío —su valor por omisión— la lista es ``['']``, ningún
``report_name`` real coincide, y la rama no se ejecuta. El bloqueo se manifiesta
donde de verdad está, en vez de propagarse a un método que ya se puede portar.

Sucesor del enganche: el mismo que ``account_move_send.py`` ya registra. Su
mitad de ``pypdf`` la cierra ``src/tools/pdf`` (construido en el bloque C); la
de ``env['ir.qweb']._render`` sigue abierta.
"""
import io

from orm.environments import context_scope
from orm.method_chain import wrap_method
from orm.registry import model_by_name

from addons.base.models.ir_actions_report import IrActionsReport
from addons.base.models.ir_config_parameter import SystemParameter
from addons.account.models.account_move_send import AccountMoveSend

#: Clave del parámetro de sistema con la lista de plantillas personalizadas que
#: sí llevan Factur-X — separada por comas, como la fuente.
CUSTOM_TEMPLATES_PARAM = 'account.custom_templates_facturx_list'


def _render_qweb_pdf_prepare_streams(self, previous, report_ref, data,
                                     res_ids=None):
    """≙ ``_render_qweb_pdf_prepare_streams`` (``odoo19c: :9-30``).

    Extiende la base: pide los flujos y, si el reporte es una de las
    plantillas personalizadas declaradas y se está rindiendo **una sola**
    factura de venta publicada, sustituye su flujo por el mismo PDF con el
    Factur-X embebido.

    Va por :func:`~orm.method_chain.wrap_method` y no por ``chain_method``
    porque el resultado de la previa es el **insumo** del cuerpo, que es la
    semántica de ``super()`` y la que ``chain_method`` no puede expresar.
    """
    collected_streams = previous(report_ref, data, res_ids=res_ids)

    custom_templates = SystemParameter.get_param(CUSTOM_TEMPLATES_PARAM,
                                                 default='')
    custom_templates = [report.strip() for report in custom_templates.split(',')]

    if (
        collected_streams
        and res_ids
        and len(res_ids) == 1
        and self._get_report(report_ref).report_name in custom_templates
    ):
        account_move = model_by_name('account.move')
        invoice = (account_move.objects.filter(pk__in=res_ids).first()
                   if account_move else None)
        if (invoice is not None and invoice.is_sale_document()
                and invoice.state == 'posted'):
            pdf_stream = collected_streams[invoice.pk]['stream']
            invoice_data = {
                'pdf_attachment_values': {'raw': pdf_stream.getvalue()},
            }
            with context_scope(custom_template_facturx=True):
                AccountMoveSend._hook_invoice_document_after_pdf_report_render(
                    invoice, invoice_data)
            collected_streams[invoice.pk]['stream'] = io.BytesIO(
                invoice_data['pdf_attachment_values']['raw'])
    return collected_streams


def apply_account_edi_ubl_cii_ir_actions_report_extensions():
    """Cuelga sobre ``base.IrActionsReport`` el único método del archivo — ≙
    ``_inherit = 'ir.actions.report'``. La llama
    ``AccountEdiUblCiiConfig.ready()``."""
    wrap_method(IrActionsReport, '_render_qweb_pdf_prepare_streams',
                _render_qweb_pdf_prepare_streams)


__all__ = ['apply_account_edi_ubl_cii_ir_actions_report_extensions']
