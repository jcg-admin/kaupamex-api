r"""``ir.actions.report`` — lo que ``account_edi_ubl_cii`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/ir_actions_report.py``
(``odoo-tools@622ddc2a``, LGPL-3, 30 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Un símbolo, bloqueado por tres piezas nombradas
================================================

``_render_qweb_pdf_prepare_streams`` es el único método del archivo: embebe el
Factur-X en PDFs de plantilla personalizada. Bloqueado por tres piezas, las
tres medidas antes de escribir:

1. **El método base que sobreescribe no existe.**

   .. code-block:: text

      grep -n "def _render_qweb_pdf_prepare_streams" \
          src/addons/base/models/ir_actions_report.py
      → 0 hits

   Es el mismo bloqueo estructural que ``account_edi/models/
   ir_actions_report.py`` ya documentó para este mismo método:
   ``IrActionsReport`` de este árbol renderiza sobre un motor **libharu**
   propio (ADR-017), no QWeb. No hay ``super()`` al que encadenarse.
2. **``env['ir.config_parameter'].sudo().get_param``** — el proxy de ``env``
   de este addon no emula ``sudo()`` (límite declarado en
   ``account_edi_common.py``).
3. **``env['account.move.send'].with_context(...)``** — ídem con
   ``with_context``, y el método que invoca
   (``_hook_invoice_document_after_pdf_report_render``) está a su vez
   bloqueado por ``pypdf`` (0 en ``uv.lock``).

Cualquiera de las tres basta; las tres juntas no cambian la forma del
desenlace. Sucesor: el mismo que ``account_edi`` ya registra para el motor
QWeb, más declarar ``pypdf`` en ``pyproject.toml`` — ninguno de los dos cae en
el write-set de este pase.

``io`` no se importa: su único consumidor es el cuerpo bloqueado.
"""
from orm.method_chain import chain_method

from addons.base.models.ir_actions_report import IrActionsReport

from .account_edi_common import _blocked


def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
    """≙ ``_render_qweb_pdf_prepare_streams`` (``odoo19c: :9-30``) —
    **bloqueado**: ver el docstring del módulo para las tres piezas."""
    _blocked('_render_qweb_pdf_prepare_streams',
             'IrActionsReport._render_qweb_pdf_prepare_streams no existe '
             '(0 hits: el motor de render de este arbol es libharu, no QWeb)')


def apply_account_edi_ubl_cii_ir_actions_report_extensions():
    """Cuelga sobre ``base.IrActionsReport`` el único método del archivo — ≙
    ``_inherit = 'ir.actions.report'``. La llama
    ``AccountEdiUblCiiConfig.ready()``."""
    chain_method(IrActionsReport, '_render_qweb_pdf_prepare_streams',
                 _render_qweb_pdf_prepare_streams)


__all__ = ['apply_account_edi_ubl_cii_ir_actions_report_extensions']
