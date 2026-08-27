r"""``ir.http`` extendido por ``account`` — la señal de recibos en la sesión: NO PORTADO.

Adaptación de Odoo ``account/models/ir_http.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 11 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03). El archivo entero de la
referencia:

.. code-block:: python

    class IrHttp(models.AbstractModel):
        _inherit = 'ir.http'

        @api.model
        def lazy_session_info(self):
            res = super().lazy_session_info()
            res['show_sale_receipts'] = self.env['ir.config_parameter'] \
                .sudo().get_param('account.show_sale_receipts')
            return res

Un solo símbolo: añade una bandera al diccionario de "info de sesión perezosa"
que el cliente web de Odoo carga al abrir cualquier página, para decidir si
el punto de venta debe mostrar el botón de "recibo de venta".

Por qué NO se porta — medido, no supuesto
============================================

Extiende ``lazy_session_info``, que **no existe** en nuestro ``IrHttp``:

.. code-block:: text

    grep -n "def lazy_session_info\|def get_frontend_session_info" \
        src/addons/base/models/ir_http.py → 0 hits

[PROVEN, medido en el pase que escribe este archivo]. Y su ausencia no es un
olvido: el propio docstring de ``src/addons/base/models/ir_http.py`` declara
la premisa completa —*"en la referencia este modelo ES la capa HTTP: […]
autentica cada petición según el auth declarado por el endpoint, despacha, y
post-procesa la respuesta. Aquí el enrutado y el despacho los hace Django
(URLconf + middleware + DRF), y la autenticación está decidida: sesión de
servidor (ADR-018) más capacidad por vista (HasCapability, DEC-11)"*. No hay
un payload único de "info de sesión perezosa" que el cliente cargue al abrir
cualquier página — cada vista DRF devuelve exactamente el payload que su
capacidad autoriza.

Portar el parche sin el método que parchea daría un símbolo que nada
encadena: el "relleno" que ``auto-audit-before-writing.md`` prohíbe.

Dónde vive de verdad el bloqueo
==================================

Dos capas por debajo:

1. **El dato en sí sí existe.** ``ir.config_parameter``/``SystemParameter``
   está portado (``src/addons/base/models/ir_config_parameter.py``), así que
   ``SystemParameter.get_param('account.show_sale_receipts')`` funcionaría
   hoy si algo lo llamara.
2. **No hay a quién dárselo.** El punto de venta (POS) de Odoo, que es el
   consumidor real de esta bandera (decide si mostrar el botón de "recibo de
   venta" en su interfaz), no está portado en este árbol — medido:
   ``grep -rln "point_of_sale\|point.of.sale" addons/ --include=*.py`` → 0
   hits [PROVEN]. Sin POS no hay UI que lea la bandera.

Sucesor
========

Si el módulo POS llega a portarse, la pregunta correcta no será *"¿cómo
porto ``lazy_session_info``?"* sino *"¿qué endpoint de bootstrap necesita el
POS, y qué le falta?"* — la respuesta se escribirá contra ese endpoint, no
contra un método QWeb-web-client que este stack no tiene. Hasta entonces
queda DESCONOCIDO con esta condición de cierre.
"""
