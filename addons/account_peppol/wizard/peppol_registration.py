"""``peppol.registration`` — el asistente de alta en la red. BLOQUEADO.

Adaptación de Odoo ``account_peppol/wizard/peppol_registration.py``
(``odoo19c: addons/account_peppol/wizard/peppol_registration.py``, 485 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

**Este módulo no declara ninguna clase** y no exporta nada. Existe para
conservar el SITIO del archivo contra la referencia y dejar el desenlace
greppeable — mismo criterio que ``account_debit_note/security/__init__.py``.

Qué es en la referencia
=========================

El asistente que da de alta a la empresa como participante Peppol: recoge
identificador (EAS + endpoint), correo, teléfono, decide si usa la conexión de
la empresa matriz, negocia con el proxy (``can_connect`` → ``create_connection``)
y deja creado el usuario de proxy. Declara **24 campos** y **21 métodos**.

Por qué está bloqueado — la arista raíz, medida
=================================================

**Su dato central es ``peppol_eas`` + ``peppol_endpoint``**, y esos dos campos
los declara ``account_edi_ubl_cii``
(``odoo19c: account_edi_ubl_cii/models/res_partner.py:43,51``) — addon que
**se está portando en otro pase, en paralelo**, y que por tanto este addon no
importa ni declara en ``depends``. Sin ellos:

- ``peppol_eas`` (``:88``) y ``peppol_endpoint`` (``:89``) —los dos campos
  ``required=True`` del asistente— no tienen origen;
- ``_get_proxy_identification(company, 'peppol')`` no puede componer el
  ``{eas}:{endpoint}`` que la red exige (ver
  ``models/account_edi_proxy_user.py``, donde el método **sí** está portado en
  su forma, con ese bloqueo declarado);
- ``_compute_peppol_warnings`` (``:169-209``), que es el corazón de la
  validación previa, comprueba precisamente ese par.

Bloqueadores de segundo orden, también medidos
================================================

- ``peppol_parent_company_id`` (``:32``, ``:130-133``) — el flujo de empresa
  matriz depende del mismo par de campos (ver ``models/res_company.py``).
- ``ir.default`` sin ``set()`` de clase — el asistente siembra el estado de
  verificación por empresa igual que ``ResCompany.create``, y ese punto ya
  está declarado bloqueado ahí.
- Los ``@api.onchange`` (``:104``, ``:110``) y los ``ir.actions.act_window``
  de retorno son mecánica del formulario del cliente web de Odoo, capa que
  este árbol no tiene.

Lo que **sí** quedó portado de este flujo
===========================================

No todo el alta está bloqueado: sus dos llamadas al proxy —``can_connect`` y
``create_connection``— viven en ``tools/peppol_iap_connector.py`` y **están
portadas enteras**. Lo mismo el alta de receptor
(``_peppol_register_sender_as_receiver``) y las dos bajas, en
``models/account_edi_proxy_user.py``. Lo que falta es el asistente que las
encadena y el par de campos que las alimenta.

**Sucesor:** tarea PENDIENTE DE ASIGNAR (resumen de este pase) — se retoma
cuando ``account_edi_ubl_cii`` aterrice. El asistente se expresará entonces
como clase sin tabla con classmethods (patrón
``account_debit_note.AccountDebitNoteWizard``), no como un modelo con 24
columnas espejo.
"""
