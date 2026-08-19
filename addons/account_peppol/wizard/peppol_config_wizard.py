"""``peppol.config.wizard`` — los servicios dados de alta. BLOQUEADO.

Adaptación de Odoo ``account_peppol/wizard/peppol_config_wizard.py``
(``odoo19c: addons/account_peppol/wizard/peppol_config_wizard.py``, 196
líneas, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

**Este módulo no declara ninguna clase** y no exporta nada. Existe para
conservar el SITIO del archivo contra la referencia y dejar el desenlace
greppeable.

Qué es en la referencia
=========================

Dos modelos transitorios:

- ``account_peppol.service`` (``:15-23``) — una fila por tipo de documento que
  la empresa tiene (o no) dado de alta en el proxy: identificador, nombre y
  si está habilitado.
- ``peppol.config.wizard`` (``:26-196``) — la pantalla que los lista, los
  sincroniza contra el proxy y permite habilitarlos o deshabilitarlos.
  **11 campos** y **8 métodos**.

Por qué está bloqueado
========================

1. **Es una proyección, no un dato.** De sus 11 campos, 6 son ``related=`` de
   ``res.company`` o del usuario de proxy (``account_peppol_edi_user``,
   ``account_peppol_proxy_state``, ``account_peppol_migration_key``,
   ``peppol_self_billing_reception_journal_id``…), todos **ya portados** en
   ``models/res_company.py``. Duplicarlos como columnas de un modelo
   transitorio sería inventar estado que hay que sincronizar — el mismo
   criterio con que se declara ``models/res_config_settings.py``.
2. **``service_info`` (``:57``) es ``Html`` compuesto para el formulario**
   (``_compute_service_info``, ``:82-103``): cliente web de Odoo.
3. **``peppol_activate_self_billing``** (``:41-48``, con su ``compute`` e
   ``inverse``) opera sobre ``peppol_activate_self_billing_sending`` y el
   diario de autofacturación — los dos campos **están portados** en
   ``models/res_company.py``, y la fuente los marca *Deprecated*.

Lo que **sí** quedó portado de este flujo
===========================================

El trabajo real de la pantalla son dos llamadas al proxy, y las dos están
portadas en ``models/account_edi_proxy_user.py``:

- ``_peppol_get_services`` — leer qué servicios tiene dados de alta la
  empresa (es lo que ``_compute_service_json``, ``:71-80``, consume);
- ``_peppol_auto_deregister_services`` — declarado bloqueado ahí, por el
  registro de módulos.

Y el catálogo de tipos de documento que la pantalla ofrece está portado
verbatim en ``ResCompany._peppol_modules_document_types``.

**Sucesor:** tarea PENDIENTE DE ASIGNAR (resumen de este pase) — cuando exista
la capa de configuración DRF, esta pantalla es un endpoint sobre
``_peppol_get_services`` y el catálogo, sin modelo transitorio.
"""
