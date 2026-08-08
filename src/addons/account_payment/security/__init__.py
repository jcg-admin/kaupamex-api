"""``security/`` de ``account_payment`` — **0 de 4 filas portadas**.

La referencia trae dos archivos:

- ``odoo19c: account_payment/security/ir.model.access.csv`` (3 filas): ACL
  de lectura/escritura/creación sobre ``payment.link.wizard``,
  ``payment.refund.wizard`` y ``payment.transaction``, todas ligadas al
  grupo ``account.group_account_invoice``.
- ``odoo19c: account_payment/security/ir_rules.xml`` (1 regla): resetea el
  dominio de acceso a tokens para ese mismo grupo (``[(1, '=', 1)]`` —
  acceso total).

Este stack **no tiene modelo de grupos Odoo** (``ir.model.access`` /
``ir.rule``): la autorización de vistas es por **capacidad** DRF
(``HasCapability``, ``api: CLAUDE.md`` — fail-closed, sin capacidad
declarada → 403), y el aislamiento por fila es explícito en el queryset de
cada vista, no un dominio declarativo tipo ``ir.rule`` (ver
``payment/controllers/portal.py``, función ``_own_order``).

Ninguna de las 4 filas es portable literalmente por esa razón estructural
—no por pereza—, y además ninguna tiene destino: los dos wizards
(``payment.link.wizard``, ``payment.refund.wizard``) están fuera del
alcance explícito de esta tarea (``wizards/``, no listado), y
``payment.transaction`` (≙ ``Payment`` aquí) ya tiene su propia superficie
DRF en ``payment/controllers/portal.py``, gateada por la capacidad
``account.payments`` que ``base`` ya siembra en todos los roles
(``payment/controllers/portal.py``, docstring). Ese addon **no** se toca
desde aquí (fuera del alcance: "no toques ningún otro addon").

Condición de cierre: si ``controllers/`` de este addon gana su primera
ruta real (ver ``controllers/__init__.py``), la capacidad a declarar es la
misma —``account.payments``— extendida a facturas: no hace falta una
capacidad nueva (mismo criterio que ya fijó H-API-283 para el addon
``payment``).
"""
