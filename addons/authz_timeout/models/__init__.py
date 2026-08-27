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
#   ir_http.py          → ir_http.py — PENDIENTE: 8 símbolos de la referencia
#                         sin contraparte (_authenticate, _check_identity,
#                         _handle_error, _must_check_identity,
#                         _session_info_common_auth_timeout,
#                         _set_session_inactivity, get_frontend_session_info,
#                         session_info). El endpoint REST existe
#                         (`controllers/main.py`, GET …/timeout/check-identity/)
#                         pero el enganche del dispatcher no. Tarea #83.
#   res_groups.py       → res_groups.py — PENDIENTE: create/unlink/write, los
#                         tres lados de escritura que invalidan el cache de
#                         timeouts por grupo. Tarea #83.
#   res_users.py        → res_users.py (los tres _get_lock_timeout*).
#   ir_websocket.py     → PENDIENTE, y NO bloqueado: la capa existe aquí en
#                         `addons/bus/models/ir_websocket.py`, que declara la
#                         política de suscripción como funciones de módulo
#                         (build_bus_channel_list, prepare_subscribe_data). Lo
#                         que falta es el eslabón de este addon sobre ellas.
#                         Medido 2026-08-27; el gate lo daba por ARCHIVO NO
#                         PORTADO porque busca una clase `IrWebsocket` y aquí
#                         el mecanismo son funciones. Tarea #83.
