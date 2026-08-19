"""``res.config.settings`` extendido por ``account_peppol``. BLOQUEADO.

Adaptación de Odoo ``account_peppol/models/res_config_settings.py``
(``odoo19c: addons/account_peppol/models/res_config_settings.py``, 177 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

**Este módulo no instala nada** y no exporta función ``apply_*``. Existe para
conservar el SITIO del archivo contra la referencia y dejar el desenlace
greppeable.

Qué es en la referencia
=========================

La **pantalla de configuración** de Peppol: 15 campos ``related=`` que
proyectan sobre el asistente de ajustes lo que vive en ``res.company`` y en el
usuario de proxy, más 11 botones que disparan las acciones de conexión.

Por qué está bloqueado — dos razones, las dos medidas
=======================================================

1. **El modelo destino no está portado.** ``res.config.settings`` es el
   asistente de ajustes de Odoo; medido, ``addons/account/models/
   res_config_settings.py`` de este árbol **no declara ninguna clase**
   (``grep -n "^class " …`` → 0 hits). Sin destino no hay ``_inherit``.
2. **Los 15 campos son ``related=`` puros.** No aportan dato ni lógica: leen y
   escriben ``company_id.*`` y ``account_peppol_edi_user.*``, que **ya están
   portados** en ``models/res_company.py`` y
   ``models/account_edi_proxy_user.py``. Duplicarlos aquí como columnas sería
   inventar estado que hay que sincronizar. Es el mismo criterio con que este
   árbol excluye ``views/``: la pantalla es del cliente, y el cliente de este
   proyecto es React.

Los 11 botones y dónde vive hoy lo que hacen
==============================================

.. list-table::
   :header-rows: 1
   :widths: 46 54

   * - Botón (línea)
     - Dónde vive su trabajo en este árbol
   * - ``button_peppol_register_sender_as_receiver`` (``:145-148``)
     - **portado** — ``AccountEdiProxyUser._peppol_register_sender_as_receiver``.
   * - ``button_peppol_deregister`` (``:163-169``)
     - **portado** — ``_peppol_deregister_participant``.
   * - ``button_reconnect_this_database`` (``:150-153``)
     - **portado** — ``_peppol_out_of_sync_reconnect_this_database``.
   * - ``button_disconnect_this_database`` (``:155-161``)
     - **portado** — ``_peppol_out_of_sync_disconnect_this_database``.
   * - ``button_peppol_disconnect_branch_from_parent`` (``:129-143``)
     - BLOQUEADO — depende de ``peppol_parent_company_id``
       (``account_edi_ubl_cii``).
   * - ``button_peppol_reregister`` (``:171-177``)
     - BLOQUEADO — reinicia la configuración y abre el asistente de alta
       (``wizard/peppol_registration.py``, bloqueado).
   * - ``action_open_peppol_form`` (``:110-114``) /
       ``button_open_peppol_config_wizard`` (``:116-127``)
     - no portados — navegación pura (``ir.actions.act_window`` del cliente
       web), mismo criterio que ``project_account.action_profitability_items``.
   * - ``_get_peppol_proxy_type`` (``:34-41``)
     - **portado** en ``ResCompany._get_peppol_proxy_type``.
   * - ``_compute_peppol_use_parent_company`` (``:43-54``) /
       ``_compute_peppol_participation_role`` (``:56-64``) /
       ``_inverse_peppol_participation_role`` (``:66-76``)
     - BLOQUEADOS — el rol de participación (emisor / receptor / ninguno) se
       deriva de ``account_peppol_proxy_state`` (portado) **y** de la empresa
       matriz Peppol (bloqueada).
   * - ``_compute_account_peppol_contact_email`` (``:78-80``) /
       ``_inverse_account_peppol_contact_email`` (``:82-108``)
     - BLOQUEADO el ``inverse`` — notifica al proxy el cambio de correo con
       ``_call_peppol_proxy`` (portado) pero sobre el campo del asistente, que
       no existe. El ``compute`` **sí** está portado, en
       ``ResCompany._compute_account_peppol_contact_email``.

**Sucesor:** tarea PENDIENTE DE ASIGNAR (resumen de este pase) — cuando exista
la capa de configuración DRF de este árbol, esta pantalla se expresa como
endpoint sobre los campos de ``res.company`` que ya están portados, no como
un modelo transitorio con 15 columnas espejo.
"""
