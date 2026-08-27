r"""``ir.actions.report`` — lo que ``account_edi`` le cuelga (≙ ``_inherit``).

Adaptación de ``addons/account_edi/models/ir_actions_report.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, ``odoo19c:``,
LGPL-3, 47 líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

Un símbolo — bloqueado por DOS piezas ausentes, medidas antes de escribir
=============================================================================

``_render_qweb_pdf_prepare_streams`` (el único método de la referencia)
embebe los adjuntos EDI dentro del PDF de la factura ya renderizado.
Bloqueado por dos piezas concretas, ninguna presente en este árbol:

1. **El método base que sobreescribe no existe.** ``IrActionsReport``
   (``src/addons/base/models/ir_actions_report.py:305``) renderiza con
   ``render``/``_render_pdf`` sobre un motor **libharu** propio (ADR-017),
   no QWeb — mismo bloqueo estructural que ``account/models/
   ir_actions_report.py`` ya documentó para sus cuatro símbolos QWeb.
   Medido en este mismo pase:

   .. code-block:: text

      grep -n "def _render_qweb_pdf_prepare_streams" \
          src/addons/base/models/ir_actions_report.py
      → 0 hits

   [PROVEN]. No hay ``super()._render_qweb_pdf_prepare_streams(...)`` al
   que ``chain_method`` pueda encadenarse — el método base que la
   referencia extiende sencillamente no existe en este stack.

2. **``odoo.tools.pdf.OdooPdfFileReader``/``OdooPdfFileWriter`` requieren
   ``pypdf``/``PyPDF2``.** Medido (regla 1 de la tanda,
   ``grep -i pypdf uv.lock`` / ``grep -i pypdf2 uv.lock``):

   .. code-block:: text

      grep -ic pypdf /home/user/kaupamex-api/uv.lock    → 0
      grep -ic pypdf2 /home/user/kaupamex-api/uv.lock   → 0

   [PROVEN]. Misma ausencia que ``account/models/
   account_document_import_mixin.py`` ya midió con el intérprete del
   proyecto (``uv run python3 -c "import pypdf"`` → ``ModuleNotFoundError``)
   para el mismo trío de librerías.

Cualquiera de las dos piezas basta para bloquear el método entero — las dos
ausentes hace el bloqueo doblemente cierto, no lo cambia de forma. Desenlace:
**bloqueado por piezas concretas**, sin construcción posible hoy (construir
requeriría además reescribir el motor de render a QWeb — fuera del alcance de
un solo símbolo de un addon satélite). Sucesor: el mismo que ``account/
models/ir_actions_report.py`` ya registra para el motor QWeb en general +
declarar ``pypdf`` en ``pyproject.toml`` (sucesor ya anotado en
``account_document_import_mixin.py``).
"""


def apply_account_edi_extensions():
    """No-op documentado — el único símbolo del archivo está bloqueado (ver
    el docstring del módulo). Se define por uniformidad con
    ``AccountEdiConfig.ready()``, mismo criterio que ``account/models/
    ir_attachment.py::apply_account_extensions`` para su propio caso de
    "archivo sin nada colgable"."""
    return None
