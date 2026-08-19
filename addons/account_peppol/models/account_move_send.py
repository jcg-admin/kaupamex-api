"""``account.move.send`` extendido por ``account_peppol``. BLOQUEADO.

Adaptación de Odoo ``account_peppol/models/account_move_send.py``
(``odoo19c: addons/account_peppol/models/account_move_send.py``, 364 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

**Este módulo no instala nada** y no exporta función ``apply_*``: sus 17
símbolos están bloqueados por la misma arista raíz. Existe para conservar el
SITIO del archivo contra la referencia y dejar el desenlace greppeable — y
para que el día que la arista caiga, el trabajo pendiente esté enumerado en
vez de haber que releer 364 líneas de la fuente.

Qué es en la referencia
=========================

El **flujo de envío** por Peppol: elegir Peppol como método de envío cuando el
contacto lo admite, generar el UBL, mandarlo al proxy, y volcar el resultado
en cada asiento. Es la mitad de salida del addon (la de entrada vive en
``models/account_edi_proxy_user.py``).

La arista raíz — ``account_edi_ubl_cii`` + los campos de envío de ``account``
==============================================================================

Dos bloqueadores, ambos medidos, y ninguno resoluble desde este write-set:

1. **``account_edi_ubl_cii``** — el módulo importa ``PEPPOL_LIST`` y
   ``PEPPOL_DEFAULT_COUNTRIES`` de ``account/models/company.py`` (0 hits en
   este árbol) y construye el XML con el generador UBL de ese addon. **Se está
   portando en otro pase, en paralelo**: este addon no lo importa ni lo
   declara en ``depends``.
2. **El marco de envío de ``account``** — medido, **0 hits** de cada uno en
   este árbol: ``invoice_sending_method``, ``invoice_edi_format``,
   ``sending_data`` (como campo del asiento), ``display_send_button``,
   ``is_self_billing``, ``is_sale_document``, ``commercial_partner_id`` (en el
   asiento). El ``AccountMoveSend`` local
   (``addons/account/models/account_move_send.py``) **sí existe** y su propio
   docstring ya declara que todo lo que orquesta un EDI concreto está
   bloqueado: *"ningún addon l10n_*_edi/account_edi_* está portado"*. Este
   archivo es la otra cara de esa misma declaración.

Los 17 símbolos, y qué hace cada uno
======================================

.. list-table::
   :header-rows: 1
   :widths: 46 54

   * - Símbolo (línea)
     - Qué hace en la referencia
   * - ``_get_default_sending_methods`` (``:20-30``)
     - añade ``'peppol'`` al conjunto por defecto cuando el contacto puede
       recibir por la red.
   * - ``_generate_and_send_invoices`` (``:32-41``)
     - punto de entrada del envío; llama a ``_do_peppol_pre_send``.
   * - ``_get_peppol_what_is_peppol_alert`` (``:43-71``)
     - la alerta «¿qué es Peppol?» del formulario de envío.
   * - ``_get_peppol_what_is_peppol_message`` (``:73-76``) /
       ``_get_peppol_partner_want_peppol_message`` (``:78-81``) /
       ``_get_peppol_what_is_pdp_message`` (``:83-84``)
     - los tres textos de esa alerta.
   * - ``_get_alerts`` (``:86-148``)
     - reúne las alertas por estado del contacto y de la empresa.
   * - ``_get_peppol_document_params`` (``:150-185``)
     - arma el ``params`` del documento que se manda al proxy: identificadores
       de emisor y receptor, tipo de documento, el XML en base64.
   * - ``_get_default_invoice_edi_format`` (``:187-192``)
     - fija el formato UBL por defecto cuando el envío es por Peppol.
   * - ``_get_mail_layout`` (``:194-196``)
     - la plantilla de correo con el bloque informativo de Peppol.
   * - ``_do_peppol_pre_send`` (``:198-205``)
     - verifica el endpoint del contacto antes de enviar.
   * - ``_is_applicable_to_company`` (``:207-212``) /
       ``_is_applicable_to_move`` (``:214-229``)
     - las dos guardas de aplicabilidad del método ``peppol``.
   * - ``_hook_if_errors`` (``:231-242``)
     - marca ``peppol_move_state = 'error'`` en los asientos que fallaron.
   * - ``_call_web_service_after_invoice_pdf_render`` (``:244-278``)
     - el punto donde el envío real ocurre, ya con el PDF generado.
   * - ``_send_peppol_documents`` (``:280-338``)
     - manda el lote al proxy y escribe ``peppol_message_uuid`` y estado.
   * - ``action_what_is_peppol_activate`` (``:340-364``)
     - abre el asistente de alta desde la alerta.

**Sucesor:** tarea PENDIENTE DE ASIGNAR (resumen de este pase) — se retoma
cuando ``account_edi_ubl_cii`` esté portado **y** ``account`` reciba los
campos de envío listados arriba. Es el símbolo que más valor desbloquea del
addon: sin él, Peppol recibe pero no envía.
"""
