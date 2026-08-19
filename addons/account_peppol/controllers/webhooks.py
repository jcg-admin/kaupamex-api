"""Rutas de webhook del proxy Peppol. BLOQUEADAS por el cableado de URLs.

Adaptación de Odoo ``account_peppol/controllers/webhooks.py``
(``odoo19c: addons/account_peppol/controllers/webhooks.py``, 62 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

**Este módulo no declara ninguna vista** y no exporta nada. Existe para
conservar el SITIO del archivo contra la referencia y dejar el desenlace
greppeable.

Porte símbolo por símbolo — 3 rutas, las 3 bloqueadas
=======================================================

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Ruta (línea)
     - Qué hace / desenlace
   * - ``POST /peppol/webhook/new_message/<token>`` (``:7-24``)
     - el proxy avisa de que hay documentos nuevos que recoger; dispara el
       cron de recogida. BLOQUEADO — ver abajo.
   * - ``POST /peppol/webhook/message_update/<token>`` (``:26-43``)
     - el proxy avisa del cambio de estado de un documento enviado; dispara el
       cron de estados. BLOQUEADO.
   * - ``POST /peppol/webhook/user_update/<token>`` (``:45-62``)
     - el proxy avisa de un cambio en el participante; dispara el cron de
       estado del participante. BLOQUEADO.

Por qué están bloqueadas — y qué **sí** quedó portado
=======================================================

Las tres rutas son **la misma forma**: verifican el token, resuelven el
usuario de proxy y disparan un cron. De esas tres piezas, **dos ya están
portadas** en ``models/account_edi_proxy_user.py``:

- la verificación del token — ``_get_user_from_token``, construido sobre
  ``django.core.signing`` (la fuente usa ``tools.verify_hash_signed``, que no
  existe aquí: 0 hits medidos);
- los tres crons — ``_cron_peppol_get_new_documents``,
  ``_cron_peppol_get_message_status``, ``_cron_peppol_get_participant_status``.

Lo que falta es **la ruta**, y su bloqueo es de alcance, no de mecanismo:

1. **El cableado de URLs vive fuera de este write-set.** Este árbol monta cada
   controlador en ``src/config/urls.py`` (precedente:
   ``addons/account_debit_note/controllers/urls.py`` montado en
   ``config/urls.py:202``). Escribir aquí una vista DRF sin ese ``include``
   dejaría código inalcanzable y no verificable — que es exactamente lo que
   un porte no debe producir.
2. **``@http.route(auth='public', csrf=False)``** exige además decidir la
   política de autenticación y CSRF de una ruta pública firmada, decisión de
   arquitectura que este árbol toma en ``addons/authz``, no en un addon de
   contabilidad.

**Sucesor:** tarea PENDIENTE DE ASIGNAR (resumen de este pase) — tres vistas
DRF ``@api_view(['POST'])`` con ``permission_classes = [AllowAny]`` (la firma
del token **es** la autenticación) más su ``urls.py`` y el ``include`` en
``config/urls.py``. El trabajo de negocio ya está hecho: la vista sería
verificar y llamar.
"""
