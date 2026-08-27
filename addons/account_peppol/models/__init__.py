"""Modelos del addon ``account_peppol`` — un archivo por archivo de la fuente.

Adaptación de Odoo ``account_peppol`` (``odoo19c: addons/account_peppol/``,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Este addon **no declara modelos propios**: como la referencia, extiende los que
ya existen (``res.company``, ``res.partner``, ``account.move``,
``account.journal``, ``account_edi_proxy_client.user``). Por eso aquí no se
importa nada — sin modelo concreto no hay clase que registrar en el import de
la app; las extensiones corren en ``AccountPeppolConfig.ready()``.

Los diez archivos, y cuál instala algo
========================================

**Instalan (5)** — su ``apply_*`` está en ``AccountPeppolConfig._EXTENSIONES``:

- ``account_edi_proxy_user.py`` — el vocabulario Peppol sobre el usuario de
  proxy: hosts, endpoints, errores, ciclo de vida del participante, crons,
  webhook. 21 de 33 símbolos portados.
- ``res_company.py`` — el estado del participante y su configuración.
  30 de 47 símbolos portados.
- ``res_partner.py`` — el estado de verificación del contacto y la consulta al
  SMP. 6 de 20 símbolos portados.
- ``account_move.py`` — el identificador y el estado del envío del asiento.
  6 de 10 símbolos portados.
- ``account_journal.py`` — la marca de diario Peppol. 3 de 7 símbolos.

**Documentación (5)** — bloqueados enteros, sin ``apply_*``, y ``ready()`` no
los carga:

- ``account_edi_common.py``, ``account_edi_ubl_xml.py``,
  ``account_edi_xml_ubl_bis3.py`` — los tres extienden modelos de
  ``account_edi_ubl_cii``, addon que **se está portando en otro pase, en
  paralelo**. Este addon no lo importa ni lo declara en ``depends``: la arista
  la reconcilia el orquestador.
- ``account_move_send.py`` — el flujo de **salida** (generar el UBL y enviarlo).
  Bloqueado por la misma arista más los campos de envío de ``account``
  (medidos, 0 hits: ``invoice_sending_method``, ``invoice_edi_format``,
  ``sending_data``, ``display_send_button``, ``is_self_billing``,
  ``is_sale_document``).
- ``res_config_settings.py`` — la pantalla de ajustes; su modelo destino no
  está portado y sus 15 campos son ``related=`` de lo que ya vive en
  ``res_company``.

Cada archivo lleva en su docstring la tabla símbolo por símbolo con el
desenlace y su medición.
"""
