"""Rutas de autenticación del alta Peppol (itsme®). BLOQUEADAS.

Adaptación de Odoo ``account_peppol/controllers/authentication.py``
(``odoo19c: addons/account_peppol/controllers/authentication.py``, 83 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

**Este módulo no declara ninguna vista** y no exporta nada. Existe para
conservar el SITIO del archivo contra la referencia.

Porte símbolo por símbolo — 2 rutas, las 2 bloqueadas
=======================================================

- ``GET /peppol/authentication/callback`` (``:12-54``) — la vuelta del
  usuario tras identificarse con un proveedor de identidad (itsme® en
  Bélgica): valida el ``connect_token``, guarda el ``auth_token`` y redirige
  al asistente de alta con el resultado.
- ``POST /peppol/authentication/webhook`` (``:56-83``) — la vuelta
  *servidor a servidor* del mismo proceso.

Ambas **BLOQUEADAS por ``wizard/peppol_registration.py``**: su único
consumidor es el asistente de alta, que está bloqueado por
``account_edi_ubl_cii`` (ver su docstring). Bloqueador de segundo orden, el
mismo que ``controllers/webhooks.py``: el cableado de URLs vive en
``src/config/urls.py``, fuera de este write-set, y la política de una ruta
``auth='public', csrf=False`` la fija ``addons/authz``, no un addon de
contabilidad.

**Sucesor:** tarea PENDIENTE DE ASIGNAR (resumen de este pase) — el mismo pase
que desbloquee el asistente de alta.
"""
