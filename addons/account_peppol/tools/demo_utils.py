"""``demo_utils`` — el arnés de modo demo. BLOQUEADO, no se instala.

Adaptación de Odoo ``account_peppol/tools/demo_utils.py``
(``odoo19c: addons/account_peppol/tools/demo_utils.py``, 180 líneas, LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

**Este módulo no instala nada** y por eso no exporta ninguna función: los 9
símbolos de la referencia están bloqueados por piezas ausentes y medidas.
Existe para conservar el SITIO del archivo contra la referencia y dejar el
desenlace greppeable — mismo criterio que
``account_debit_note/security/__init__.py``. No es un *stub*: en particular
**no** se declara un ``handle_demo`` que devuelva la función sin tocarla,
porque eso convertiría en silencio el modo demo en modo real (:ref:`h-api-733`).

Qué es en la referencia
=========================

``handle_demo`` es un decorador que intercepta ciertos métodos cuando la
empresa está en ``edi_mode == 'demo'`` y los sustituye por un simulacro:
devuelve una factura de proveedor de mentira, finge el alta del participante,
finge la baja. Sostiene el flujo de demostración sin tocar el proxy real.

Porte símbolo por símbolo — 9 símbolos, los 9 bloqueados
==========================================================

Todos comparten la misma raíz, así que el desenlace se agrupa:

- ``DEMO_BILL_PATH`` / ``DEMO_ENC_KEY`` / ``DEMO_PRIVATE_KEY`` (``:8-10``),
  ``get_demo_vendor_bill`` (``:16-28``) — **BLOQUEADOS por los tres archivos
  binarios de la referencia** (``tools/demo_bill``, ``tools/enc_key``,
  ``tools/private_key.pem``): son datos de demostración de Odoo, no código, y
  este árbol no porta la capa de datos de la referencia (criterio ya
  establecido: ``project_todo/data/``, ``account_debit_note/views/``).
  Bloqueador de segundo orden: ``odoo.tools.misc.file_open`` no existe aquí —
  medido, ``grep -rn "def file_open" src/tools/*.py`` → **0 hits**.
- ``_mock_call_peppol_proxy`` (``:34-93``) — además **BLOQUEADO por el
  identificador externo** ``account_peppol.ir_cron_peppol_get_new_documents``,
  que vive en ``data/cron.xml`` de la referencia (XML de datos, no portado) y
  se resuelve con ``env.ref``.
- ``_mock_get_peppol_verification_state`` (``:95-103``),
  ``_mock_check_peppol_participant_exists`` (``:105-108``),
  ``_mock_create_connection`` (``:110-143``),
  ``_mock_peppol_deregister_participant`` (``:145-148``),
  ``_mock_can_connect`` (``:150-154``) — **BLOQUEADOS por su simulacro**: cada
  uno fabrica la respuesta del proxy para su método real. Sin el arnés
  completo, instalar uno solo daría un modo demo a medias, que es peor que no
  tenerlo.
- ``_demo_behaviour`` (``:156-168``) / ``handle_demo`` (``:170-180``) —
  **BLOQUEADOS** por lo anterior: el mapa apunta a los simulacros y el
  decorador los aplica.

Consecuencia declarada sobre los métodos que lo llevan
=========================================================

En la referencia, ``@handle_demo`` decora
``ResPartner._check_peppol_participant_exists``,
``ResPartner._get_peppol_verification_state``,
``Account_Edi_Proxy_ClientUser._call_peppol_proxy``,
``_peppol_deregister_participant`` y las dos llamadas de
``PeppolIAPConnector``. En este árbol **esos métodos se portan SIN el
decorador**, y cada uno lo declara en su docstring. El efecto es que el modo
``demo`` se comporta como cualquier otro modo —intenta la llamada real y falla
si no hay proxy—, en vez de fingirla. Es una divergencia declarada, no un
olvido.

**Sucesor:** tarea PENDIENTE DE ASIGNAR (resumen de este pase) — se retoma
cuando se decida si el modo demo de Peppol se sostiene con fixtures propias de
este árbol (``tests/fixtures/``) en vez de con los binarios de la referencia.
"""
