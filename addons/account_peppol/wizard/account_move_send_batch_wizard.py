"""``account.move.send.batch.wizard`` extendido por ``account_peppol``. BLOQUEADO.

Adaptación de Odoo ``account_peppol/wizard/account_move_send_batch_wizard.py``
(``odoo19c: addons/account_peppol/wizard/account_move_send_batch_wizard.py``,
14 líneas, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

**Este módulo no declara ninguna clase** y no exporta nada. Existe para
conservar el SITIO del archivo contra la referencia.

Porte símbolo por símbolo — 1 símbolo, bloqueado
==================================================

``action_send_and_print`` (``:7-14``) — **BLOQUEADO** por sus tres llamadas,
las tres de ``models/account_move_send.py`` (bloqueado entero por
``account_edi_ubl_cii`` más los campos de envío de ``account``, medidos):
``_get_default_sending_methods``, ``_is_applicable_to_move`` y
``_do_peppol_pre_send``.

Qué hace en la referencia, para cuando se retome: antes de mandar un lote a
imprimir/enviar, si alguno de los asientos va por Peppol, dispara la
verificación previa; y si de ella sale que la empresa aún no está dada de
alta, **devuelve la acción de alta en vez de enviar**. Es la puerta que evita
que un envío masivo falle documento a documento.

**Sucesor:** tarea PENDIENTE DE ASIGNAR — el mismo pase que desbloquee el
flujo de salida.
"""
