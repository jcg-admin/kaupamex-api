# Adaptación de Odoo `auth_timeout` (odoo-tools@622ddc2a, odoo19c:, LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03). La licencia se derivó
# del manifiesto de la fuente, no se afirmó: `"license": "LGPL-3"`.
#
# El addon aporta el eje que `authz_reauth` NO cubre, y que H-API-767 dejó
# nombrado como la tarea #640: el **candado por tiempo**. Los dos ejes son
# ortogonales y conviven:
#
#   authz_reauth   step-up POR ACCIÓN     — esta acción es sensible, confirma
#                                            identidad antes de ejecutarla
#   authz_timeout  candado POR TIEMPO     — pasó el umbral, confirma identidad
#                                            (o cierra sesión) sin importar qué
#                                            acción venga
#
# COBERTURA MEDIDA — 19 de 35 defs de código (porte-completo-no-parcial.md)
# ========================================================================
#
# La referencia tiene 8 archivos de código con 35 defs de clase (más 21 en su
# suite, fuera de este conteo). Portados en este pase:
#
#   models/res_groups.py    16 defs + 2 funciones de módulo + 13 atributos
#   models/res_users.py      3 defs
#
# NO portados, cada uno con su sucesor registrado:
#
#   models/ir_http.py        8 defs + CheckIdentityException  ─┐
#   controllers/main.py      3 defs                            ├─ tarea #714
#   controllers/web_home.py  1 def                             │
#   controllers/auth_passkey_webauthn.py  1 def               ─┘
#   models/ir_websocket.py   2 defs   → tarea #715 (DESCONOCIDO: sin websocket)
#   models/auth_totp_device.py  1 def → tarea #716 (falta auth_totp.device)
#
# Y un símbolo consumido que este árbol no tiene: `_mfa_type`, que vive en
# `auth_totp` y no aquí → tarea #713.
#
# El corte no es de conveniencia: lo portado es el EJE DE DATOS completo
# —dónde se configura el umbral, cómo se resuelve el más corto entre los grupos
# implicados, y cómo lo consulta el usuario—, y lo ausente es la capa HTTP que
# lo consume, que exige una decisión de integración con `assert_session_fresh`
# (ver #714).
{
    'name': 'Candado por tiempo de sesión',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': (
        'lock_timeout absoluto y lock_timeout_inactivity, configurables por '
        'grupo, con su bandera de segundo factor'
    ),
    # `depends` MEDIDO contra los imports reales. La referencia declara
    # ['auth_totp', 'auth_totp_mail', 'auth_passkey', 'bus'] — sus segundos
    # factores más el canal de presencia. Aquí:
    #
    # - `bus` NO se declara: su única razón allá es `ir_websocket.py`, que este
    #   pase no porta (#715).
    # - `authz_totp_mail` NO se declara: su papel allá es el reenvío del código
    #   por correo desde `controllers/main.py`, que tampoco se porta (#714).
    # - `authz_passkey` SÍ: `_get_auth_methods` lee `user.passkeys`
    #   (models/res_users.py), el reverso del M2M que declara
    #   `authz_passkey/models/auth_passkey_key.py:83`.
    # - `authz_totp` SÍ: `_get_auth_methods` llama a `_mfa_type`, cuyo hogar es
    #   ese addon (#713). La arista existe hoy aunque el símbolo no.
    'depends': [
        'base',            # ResGroups (el candado) y ResUsers (su lectura)
        'authz_totp',      # _mfa_type — el segundo factor de app (#713)
        'authz_passkey',   # user.passkeys — el segundo factor WebAuthn
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
