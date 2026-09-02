r"""Lo que ``sale`` añade al reporte — ≙ ``_inherit``.

Porte BLOQUEADO — 0 de 2 símbolos

Origen: ``odoo19c: sale/models/ir_actions_report.py`` (LGPL-3 según el
``__manifest__.py`` de ``sale``: copia + adaptación con atribución).

Dos símbolos, y el archivo entero está bloqueado por **tres piezas ausentes**,
las tres medidas en este pase y no heredadas de una medición anterior:

``_render_qweb_pdf_prepare_streams`` (``odoo19c: :10-48``)
    Embebe los adjuntos EDI dentro del PDF del pedido ya renderizado.

``_is_sale_order_report`` (``odoo19c: :50-55``)
    Decide si el reporte que se está rindiendo es uno de los tres del pedido.
    No está bloqueado por sí mismo — su único consumidor es el anterior, así
    que portarlo solo lo dejaría sin llamador.

Los tres bloqueos
=================

BLOQUEADO por ``ir.actions.report._render_qweb_pdf_prepare_streams`` — el
método base que la fuente extiende no existe. El motor de reporte de
este árbol es **libharu** por ADR-017, no QWeb → ``wkhtmltopdf``, y
``_render_qweb_pdf_prepare_streams`` es uno de los diez puntos de enganche de
ese pipeline que :ref:`h-api-819` (tarea #78) ya midió ausentes:

.. code-block:: text

   grep -c "def _render_qweb_pdf_prepare_streams" \
       src/addons/base/models/ir_actions_report.py
   → 0

No hay implementación previa a la que ``wrap_method`` pueda entregarle un
``super()``. [PROVEN]

BLOQUEADO por ``pypdf`` — no está declarado ni instalado, y
``OdooPdfFileReader``/``OdooPdfFileWriter`` lo exigen:

.. code-block:: text

   grep -ic pypdf uv.lock          → 0
   grep -ic pypdf2 uv.lock         → 0
   uv run python -c "import pypdf" → ModuleNotFoundError: No module named 'pypdf'

[PROVEN]. Declararlo es una decisión del ejecutor, no del puerto.

BLOQUEADO por ``account.move._get_edi_builders`` — no existe. Lo aporta la
rama EDI, que es la Ola D de ``account`` (tarea #78):

.. code-block:: text

   grep -rn "_get_edi_builders" --include=*.py addons/ src/ | wc -l → 0

[PROVEN].

Por qué esto NO es el camino barato
====================================

``porte-completo-no-parcial.md`` admite tres desenlaces para un símbolo que no
se porta, y éste es el segundo: **bloqueo medido con sucesor registrado**. No
es divergencia declarada por comodidad — es que las tres piezas se midieron y
ninguna existe, y la primera exige reescribir el motor de reporte entero, que
es una decisión de arquitectura ya tomada en el sentido contrario (ADR-017).

Sucesor: tarea **#982**, con los tres criterios de cierre. Precedente del mismo
veredicto para dos de las tres piezas:
``addons/account_edi/models/ir_actions_report.py``.
"""

#: ≙ la cabecera que la fuente declara en su clase (``odoo19c: :8``; la
#: extensión aquí no es clase). Se porta aunque el archivo esté bloqueado —
#: el bloqueo es de los dos símbolos que la clase declararía, no de su
#: cabecera, que sigue siendo cierta: el destino es ``ir.actions.report``.
_inherit = 'ir.actions.report'


def apply_sale_report_extensions():
    """No-op declarado — los dos símbolos del archivo están bloqueados.

    Se define, y ``SaleConfig.ready()`` la invoca, por la misma razón que
    ``account_edi``: el archivo existe con su medición dentro, y el cableado
    hace visible que el bloqueo es del contenido, no del olvido de cablear.
    """
    return None
