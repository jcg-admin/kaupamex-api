"""``account.move.send.wizard`` extendido por ``account_peppol``. BLOQUEADO.

Adaptación de Odoo ``account_peppol/wizard/account_move_send_wizard.py``
(``odoo19c: addons/account_peppol/wizard/account_move_send_wizard.py``, 78
líneas, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

**Este módulo no declara ninguna clase** y no exporta nada. Existe para
conservar el SITIO del archivo contra la referencia y dejar el desenlace
greppeable.

Porte símbolo por símbolo — 4 símbolos, los 4 bloqueados
==========================================================

.. list-table::
   :header-rows: 1
   :widths: 42 58

   * - Símbolo (línea)
     - Desenlace
   * - ``_get_peppol_checkbox_label`` (``:13-14``)
     - BLOQUEADO — etiqueta de la casilla «Enviar por Peppol» del formulario
       de envío del cliente web.
   * - ``_get_peppol_checkbox_addendum_disable_reason`` (``:16-37``)
     - BLOQUEADO — el texto que explica por qué la casilla está deshabilitada;
       lee ``peppol_eas`` / ``peppol_endpoint`` del contacto
       (``account_edi_ubl_cii``) y su estado de verificación.
   * - ``_compute_sending_method_checkboxes`` (``:39-68``)
     - BLOQUEADO por ``AccountMoveSendWizard`` — el modelo transitorio
       ``account.move.send.wizard`` no existe en este árbol: medido,
       ``addons/account/wizard/account_move_send_wizard.py`` no declara una
       clase con ese ``_name`` que se pueda extender con este juego de
       casillas (su docstring ya declara bloqueado todo lo que orquesta un EDI
       concreto).
   * - ``action_send_and_print`` (``:70-78``)
     - BLOQUEADO por ``_do_peppol_pre_send`` y ``_is_applicable_to_move``, los
       dos de ``models/account_move_send.py``, bloqueado entero por
       ``account_edi_ubl_cii`` + los campos de envío de ``account``.

La arista es la misma que la de ``models/account_move_send.py``: este archivo
es su capa de formulario. **Sucesor:** tarea PENDIENTE DE ASIGNAR — el mismo
pase que desbloquee el flujo de salida.
"""
