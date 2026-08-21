# Adaptación de Odoo `auth_timeout` (odoo-tools@abe4040ec1, odoo19c:, LGPL-3) —
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
# COBERTURA MEDIDA — el addon entero, no sólo su Python
# =====================================================
#
# La fuente son **70 blobs** (`git ls-tree -r origin/main`), en cinco familias.
# Cada una tiene su veredicto; ninguna se omite en silencio
# (`porte-completo-no-parcial.md`).
#
# 1. Código Python — 8 archivos, 35 defs de clase. Cubiertos 33:
#
#      models/res_groups.py    16 defs  → portado (el eje de datos del candado)
#      models/ir_http.py        8 defs  → portado (middleware + confirmación)
#      models/res_users.py      3 defs  → portado (_get_auth_methods)
#      controllers/main.py      3 defs  → portado (las tres rutas, en REST)
#      controllers/web_home.py             1 def  ─┐ portados por ROL, no por
#      controllers/auth_passkey_webauthn.py 1 def ─┘ archivo: su cuerpo entero
#                                                     es re-declarar la exención,
#                                                     que aquí es el atributo
#                                                     `check_identity = False`
#                                                     sobre la vista (ver
#                                                     controllers/__init__.py)
#
#      models/auth_totp_device.py  1 def  → portado (el estrechamiento de la
#                                            confianza del dispositivo; su
#                                            sustrato, `auth_totp.device`, se
#                                            portó en #716)
#
#    NO cubiertos, 2 defs, con su sucesor:
#
#      models/ir_websocket.py      2 defs → #715 (sin productor de presencia)
#
#    Y tres divergencias de mecanismo declaradas en el docstring de
#    `models/ir_http.py`: #720 (session_info), #721 (webauthn), #722
#    (_check_credentials unificado).
#
# 2. `i18n/` — 50 archivos (49 `.po` + 1 `.pot`). Este árbol tiene **0**
#    directorios `i18n` sobre 120 manifiestos; el motor de traducción es #400.
#    Veredicto en #723.
#
# 3. `static/` — 4 archivos (el servicio OWL del diálogo, su scss, su tour).
#    Este árbol tiene **0** directorios `static` y **0** manifiestos con la
#    clave `'assets'`. El cliente es React y vive en `kaupamex-ui` (#488).
#    Veredicto en #724.
#
# 4. `views/` — 2 XML (`res_groups_views.xml`, `login_templates.xml`). Este
#    árbol tiene **0** archivos `.xml` y **0** manifiestos con la clave
#    `'data'`: la siembra es por migración de datos por addon (#40).
#    Veredicto en #725.
#
# 5. `tests/` — `test_auth_timeout.py`, 21 defs. Adaptados a pytest en
#    `tests/unit/authz_timeout/` y `tests/integration/authz_timeout/`.
#
# Métrica: blobs de `git ls-tree -r origin/main` sobre el addon de la fuente;
# `find`/`grep` sobre `addons/` y `src/addons/` para la superficie de aquí.
# Ciega a: cadenas traducibles sin catálogo compilado, y assets servidos desde
# `STATICFILES_DIRS` fuera del árbol de addons.
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
    # - `authz_totp_mail` SÍ, desde que `models/ir_http.py` importa
    #   `verify_totp_mail_code` y `controllers/main.py` importa
    #   `send_totp_mail_code`. La fuente la declara por la misma razón.
    # - `authz_passkey` SÍ: `_get_auth_methods` lee `user.passkeys`
    #   (models/res_users.py), el reverso del M2M que declara
    #   `authz_passkey/models/auth_passkey_key.py:83`.
    # - `authz_totp` SÍ: `_get_auth_methods` llama a `_mfa_type`, y
    #   `_check_credential` verifica el código con `services.verify_code`.
    #
    # `authz` es una dependencia TRANSITORIA, y se declara como tal.
    # `require_capability` es obligatorio por DEC-11 —ninguna vista se gatea con
    # `IsAuthenticated` a secas— y hoy sólo vive en `addons/authz/permissions.py`,
    # que 42 archivos fuera de ese addon ya consumen. Pero la familia `authz*`
    # está declarada «partición de lo que la referencia mantiene en `base`»
    # (`analisis-familias-referencia.rst`), su alineación es la tarea #20, y el
    # ciclo `base ↔ authz` que esa partición produce es la #322: `base` importa
    # de `authz` en tres archivos mientras `authz` declara `depends: ['base']`.
    # Cuando #20 mude la capacidad a `base`, esta línea desaparece y el import
    # de `controllers/main.py` cambia de raíz — no de mecanismo.
    'depends': [
        'base',              # ResGroups (el candado) y ResUsers (su lectura)
        'authz',             # TRANSITORIA (#20/#322) — require_capability, DEC-11
        'authz_totp',        # _mfa_type y services.verify_code
        'authz_totp_mail',   # verify_totp_mail_code y send_totp_mail_code
        'authz_passkey',     # user.passkeys — el segundo factor WebAuthn
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
