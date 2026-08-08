"""``account_payment`` — puente Contabilidad ↔ Framework de pagos (Odoo ``account_payment``).

Adaptación de ``odoo19c: addons/account_payment/`` (``odoo-tools@622ddc2aa
5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 — atribución y aviso de licencia
preservados, DEC-KX-03).

Divergencia estructural que gobierna todo el porte
====================================================

La referencia asume una ``payment.provider`` per-registro (journal, estado
enabled/test/disabled, métodos electrónicos por compañía) y una
``payment.transaction`` genérica (``invoice_ids`` M2M, ``token_id``,
``source_transaction_id``/``child_transaction_ids``, reconciliación con
``account.move.line``). Este árbol tiene en su lugar (``api:
src/addons/payment/models/``):

- ``PaymentGateway`` (≙ ``payment.provider``) — **enum fijo** de tres
  pasarelas (``TEST``/``MERCADOPAGO``/``PAYPAL``), sin registro por diario ni
  por compañía.
- ``Payment`` (≙ ``payment.transaction``) — anclado por FK **NOT NULL
  PROTECT** a ``sale.SaleOrder`` (``api: payment/models/payment.py:61-63``,
  H-API-97): no admite invoice ni transacción sin orden.
- ``SavedCard`` (≙ ``payment.token``).
- ``account.AccountPayment`` (``api: account/models/account_payment.py``) —
  **9 campos**, sin ``move``/``payment_method_line``/reconciliación.
- ``account.AccountMove`` — sin ``amount_residual``/``payment_state``.
- ``account.AccountJournal`` — sin métodos propios más allá de ``__str__``.

Ningún símbolo que dependa de: reconciliación (``reconcile()``), acceso
portal por token (``access_token``), chatter (``message_post``), acciones de
UI (``ir.actions.act_window``), o el árbol de compañías/plantillas contables
(``account.chart.template`` con ``.ref()``) es portable sin inventar esa
infraestructura — lo que excede el alcance de portar UN addon (sería
rediseñar ``payment``/``account`` a la vez, decisión de arquitectura que este
agente no toma unilateralmente). Se porta lo que SÍ es construible con lo que
ya existe (campos vía modelo RELATED — DEC-SALE-01, igual que
``account_add_gln.PartnerGln``/``account_debit_note.AccountMoveDebitNote`` —,
``chain_method`` para comportamiento, señales para los guards de borrado) y
se declara, con medición, lo que no.

Layout — 4 de los 9 directorios de la referencia (alcance fijado por el
ejecutor: ``models/``, ``controllers/``, ``data/``, ``security/``)
========================================================================

- ``models/`` — 7 archivos (mismo nombre que la referencia). Cada uno declara
  su ``apply_account_payment_extensions()`` (mismo nombre en los 6 que
  cuelgan algo; ``account_bank_statement_line.py`` no declara ninguna, ver
  abajo).
- ``controllers/`` — **0 rutas portadas**. Los dos archivos de la referencia
  (``payment.py``, ``portal.py``) son enteramente portal/QWeb Odoo
  (``request.render``, rutas ``jsonrpc``/``http`` con ``access_token`` de
  sesión anónima) — sin contraparte en un stack DRF headless. Y el único
  flujo con valor de negocio real, "crear la transacción de pago de una
  factura", está bloqueado por ``Payment.sale_order`` NOT NULL (ver
  ``models/account_payment.py``, sección "No portado"). Ver
  ``controllers/__init__.py``.
- ``data/`` — el único ``<record model="ir.config_parameter">`` de la
  referencia, sembrado vía ``SystemParameter`` (``api:
  base/models/ir_config_parameter.py``) en una migración — mismo patrón que
  ``account_fleet/data/fleet_service_types.py``.
- ``security/`` — 0 filas portadas (ACL por grupo Odoo; este stack autoriza
  por capacidad DRF, ``HasCapability`` — no hay modelo de grupos que
  traducir). Ver ``security/__init__.py``.

**Excluidos por alcance explícito de la tarea** (no en la lista de
directorios pedida): ``wizards/`` (4 wizards, íntegramente UI de formulario:
registrar pago, enlace de pago, reembolso, ajustes — sin vista que los
dispare, no hay superficie que exponerlos), ``views/`` (7 XML, cliente web
Odoo), ``static/``/``i18n/``/``tests/`` (ref) — mismo criterio que
``account_debit_note`` excluye sus 3 XML de vista.

Cobertura medida (conteo de símbolos de la referencia, por archivo)
=======================================================================

===================================  =========  =========  ===================
Archivo                                Símbolos   Portados   No portados
===================================  =========  =========  ===================
``models/account_payment.py``               18          8  10 (token/electrónico/action_post — ver docstring)
``models/account_payment_method.py``          1          1  0
``models/account_payment_method_line.py``     6          4  2 (auto-link por journal, acción UI)
``models/account_journal.py``                 2          2  0 (reconstruidos: no hay base que extender)
``models/account_bank_statement_line.py``     1          0  1 (base ausente + campo ausente)
``models/account_move.py``                   16          5  11 (sin estado authorized/portal/QR/UI)
``models/payment_provider.py``               10          2  8 (auto-link método↔journal, chart_template)
``controllers/payment.py``                    5          0  5 (portal Odoo, sin contraparte DRF)
``controllers/portal.py``                     5          0  5 (portal Odoo, sin contraparte DRF)
``data/ir_config_parameter.xml``              1          1  0
``security/ir.model.access.csv``              3          0  3 (ACL de grupo; aquí autorización por capacidad)
``security/ir_rules.xml``                     1          0  1 (idem)
===================================  =========  =========  ===================

Total: 69 símbolos (``18+1+6+2+1+16+10+5+5+1+3+1``), 23 portados. Ningún
símbolo no portado se omite en silencio — cada uno está en la sección "No
portado" del docstring del archivo que lo habría alojado, con la medición
que sustenta la decisión (``porte-completo-no-parcial``).

Sucesores de lo no portado
============================

Las piezas que faltan (``payment.provider`` per-registro con journal y
métodos electrónicos por compañía, ``account.move.amount_residual``/
``payment_state``, reconciliación, acceso portal a factura) son decisiones
de arquitectura que exceden este pase — no un olvido. Su condición de cierre
está documentada símbolo a símbolo en cada archivo de ``models/``; no se abre
una sub-iniciativa aquí porque ninguna de ellas es ejecutable sin antes
decidir si ``payment.Payment`` deja de estar anclado a ``sale.SaleOrder``
(H-API-97), decisión de producto que corresponde al ejecutor.
"""
