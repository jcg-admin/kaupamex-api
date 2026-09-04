# Adaptado de Odoo Community `auth_password_policy` (LGPL-3) — atribución y
# aviso de licencia preservados (DEC-KX-03).
#
# Este addon NO tiene paquete `models/`, y es una decisión, no un olvido. Se
# declara al triar la tarea #81, cuando la familia authz_* entró por primera
# vez en el alcance de `check_porte_completo` (#80) y sus dos archivos de la
# referencia salieron como ARCHIVO NO PORTADO sin nada escrito que lo explicara.
#
# La referencia importa 2 archivos; el mapa completo, sin omisiones:
#
#   res_users.py           → validators.py + data.py. La referencia cuelga
#                            `get_password_policy` y `_check_password_policy`
#                            de res.users porque su ORM no tiene otra capa;
#                            aquí la política es un VALIDADOR de Django
#                            (AUTH_PASSWORD_VALIDATORS), que es el mecanismo
#                            del stack para exactamente esto y corre en todos
#                            los caminos de cambio de contraseña, no sólo en
#                            los que llamen al método. El docstring de
#                            `validators.py` cita el código de la fuente.
#   res_config_settings.py → PENDIENTE. La razón que valdría —"la UI de ajustes
#                            de base_setup no existe aquí"— es FALSA: medido
#                            2026-08-27, `addons/base_setup` existe y once
#                            addons extienden `ResConfigSettings`. Qué
#                            superficie gobierna la config de authz_* es
#                            decisión de alcance: tarea #84.
