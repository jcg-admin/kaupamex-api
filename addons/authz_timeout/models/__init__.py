# Adaptado de Odoo Community `auth_timeout/models/__init__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
#
# Este archivo no declaraba mapa de porte. Se escribe al triar la tarea #81,
# cuando el mapa de renombre de addon (#80) puso la familia authz_* dentro del
# alcance de `check_porte_completo` por primera vez: sin mapa, cada archivo que
# falta se lee igual tanto si se decidió no portarlo como si nadie lo miró.
#
# La referencia importa 5 archivos; el mapa completo, sin omisiones:
#
#   auth_totp_device.py → auth_totp_device.py (la edad del dispositivo de
#                         confianza, que es lo que el timeout consulta).
#   ir_http.py          → ir_http.py — PORTADO, 8 de 8 defs, cada una con su
#                         nombre, como funciones de módulo más
#                         `CheckIdentityMiddleware`. El docstring del archivo
#                         lleva la tabla símbolo a símbolo y sus cuatro
#                         divergencias declaradas.
#                         CORREGIDO 2026-08-27: esta línea decía "PENDIENTE: 8
#                         símbolos de la referencia sin contraparte". Era FALSA
#                         y la escribí yo al triar #81, transcribiendo la
#                         salida del gate ("CLASE AUSENTE (8)") sin abrir el
#                         archivo. El gate busca una clase `IrHttp`; aquí el
#                         despachador es Django y el enganche un middleware.
#                         Ver H-API-831.
#   res_groups.py       → res_groups.py — PORTADO: create/unlink/write son
#                         `save` + `delete`, porque Django no separa alta de
#                         modificación. Los tres existen en la fuente sólo
#                         para invalidar la caché de `_get_lock_timeouts`, y
#                         los dos nuestros hacen eso. Divergencia 2 del
#                         docstring del archivo. Misma corrección que arriba:
#                         la línea decía PENDIENTE y el código ya los tenía.
#   res_users.py        → res_users.py (los tres _get_lock_timeout*).
#   ir_websocket.py     → BLOQUEADO por ``bus.ir_websocket`` — sus dos
#                         métodos `_update_mail_presence` y
#                         `_on_websocket_closed`, que la
#                         referencia extiende aquí, y que
#                         `addons/bus/models/ir_websocket.py` NO porta por
#                         DEC-AF-06 (transporte WebSocket descartado). Sin
#                         productor de presencia, el eslabón no tendría a quién
#                         extender. Sucesor: #87.
#
#                         Y la premisa de DEC-AF-06 caducó, medido 2026-08-27:
#                         sus dos razones eran "pg_notify no existe en MariaDB"
#                         —el motor es PostgreSQL desde ADR-028, y
#                         `src/addons/base/models/ir_cron.py:225` verifica que
#                         `pg_notify` existe en 16.13— y "exigiría ASGI,
#                         incompatible con Apache + mod_wsgi" — mod_wsgi se
#                         retiró (H-SERVER-04) y Apache es proxy inverso ante
#                         gunicorn (ADR-027). Re-decidirlo es del ejecutor:
#                         tarea #87. Ver H-API-831.
