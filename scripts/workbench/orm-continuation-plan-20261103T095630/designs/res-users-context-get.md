# Porte de res.users.context_get (res-users-context-get-0397)

Prerrequisito de `designs/ir-filters-port-19.md`: `get_filters` abre con
`self.env['res.users'].context_get()`.

## Referencia

- `odoo19c: odoo/addons/base/models/res_users.py:694-723` — `@api.model`
  `@tools.ormcache('self.env.uid')`. Lee `lang` y `tz` del usuario con
  `read(..., load=False)`; sin usuario devuelve `frozendict()`; retira `id`;
  asegura un `lang` instalado en el orden contexto → petición
  (`request.best_lang`) → idioma del partner de la empresa del usuario →
  `DEFAULT_LANG` → el primero instalado; añade `uid`; devuelve `frozendict`.
- Invalidación: `res_users.py:641-643` — `write` purga el registro entero
  (`registry.clear_cache()`) cuando las claves escritas cruzan
  `_get_invalidation_fields` (`:736-740`: `group_ids`, `active`, `lang`, `tz`,
  `company_id`, `company_ids` y los de sesión).

## Estado heredado (medido)

- `context_get`: 0 coincidencias en `src/` y `addons/`.
- `ResUsers` es un modelo de Django sin `env` (sonda:
  `hasattr(ResUsers, 'env')` → `False`); `Environment()['res.users']` devuelve
  la clase.
- El invalidador de usuarios (`_invalidate_on_user_save`, `res_users.py`)
  purga sólo el memo de grupos; nada purga la caché `default` del registro al
  cambiar `lang` o `tz`.
- `lang`/`tz` se delegan al partner (`_inherits`); `user.lang = x;
  user.save()` guarda el partner y luego el usuario con `update_fields=None`,
  así que el `post_save` del usuario sí ve la escritura (`orm/inherits.py:328`).

## Cambio

1. `ResUsers.context_get` como `classmethod` con `@api.model` y
   `@ormcache('cls._context_uid()')`. `ormcache` evalúa la clave sobre los
   parámetros del método (`tools/cache.py:169-208`); el receptor es la clase,
   que no tiene `env`, así que la clave lee el `uid` del entorno ambiental por
   un acceso de clase, `_context_uid`, que devuelve `Environment().uid`. Es
   el mecanismo de enlace (divergencia de enlace ya declarada para los
   métodos de modelo portados como `classmethod`), no un cambio de clave.
2. El cuerpo, en el orden de la fuente: lee `lang` y `tz` del usuario del
   `uid`; sin usuario, `frozendict()`; idiomas de
   `res.lang.get_installed()`; la petición aporta su idioma por
   `get_current_request()` cuando la hay; luego el `lang` del partner de la
   empresa del usuario, `DEFAULT_LANG` y el primero instalado; `uid`;
   `frozendict`.
3. Invalidación: el receptor de guardado del usuario purga además la caché
   `default` del registro de la base de la fila cuando la escritura toca un
   campo de `_get_invalidation_fields` (con `update_fields=None`, siempre,
   como ya hace para los grupos).

## Pruebas

- `tests/integration/base/test_res_users_context_get.py`: devuelve `lang`,
  `tz` y `uid` sin `id`; un `lang` no instalado cae al de la empresa y luego a
  `en_US`; un `uid` sin usuario da `{}`; dos llamadas con el mismo `uid`
  devuelven el mismo objeto (memorizado); cambiar `lang` del usuario y
  guardar lo refleja en la llamada siguiente (invalidación).

## Anulación

- Retirar la purga del receptor: cae exactamente el caso de invalidación.
- Retirar el `ormcache`: cae exactamente el caso de memorización.

## Adenda: la rama de la petición y la forma del cambio

- `request.best_lang` y `DEFAULT_LANG` viven en `odoo19c: odoo/http.py`
  (`:1909-1922` y `:231`), que no tiene contraparte en el árbol. Se portan los
  dos símbolos junto a `get_current_request` en
  `src/addons/base/models/ir_http.py`, el hogar declarado del enlace
  petición→entorno: `best_lang(request)` lee `Accept-Language` con el
  analizador de Django, que ordena por calidad como `accept_languages.best`
  de werkzeug (sonda: `es-MX,es;q=0.9` → `es-mx` primero), y `babel` separa
  idioma y territorio como en la fuente. El resto de `http.py` no entra.
- Los dos métodos nuevos van al final del cuerpo de `ResUsers` y dos imports
  existentes se pliegan (`from datetime import timedelta` → `datetime.timedelta`;
  los dos `from django.contrib.auth import …` en uno): el gate de estilo
  identifica cada infracción por la posición de su sentencia, y sin esto 76
  infracciones heredadas se leían como nuevas.

## Medido

- `tests/integration/base/test_res_users_context_get.py`: 7 passed; antes del
  código, 7 failed (5 por `context_get` ausente).
- Anulación A (sin la purga del receptor): cae exactamente
  `test_writing_the_lang_purges_the_memo`. Anulación B (sin `ormcache`): cae
  exactamente `test_it_is_memoized_per_uid`. Restauradas con `cmp`.
- Subconjunto derivado ancho, porque la purga es transversal
  (`ResUsers|res_users|create_user|ormcache|clear_cache|ir_http|CaptureQueriesContext|assertNumQueries|django_assert_num_queries`,
  306 archivos, `-n 4`): 4150 passed, 11 skipped, 6 xfailed.

## Cuerpo tocado por el plegado de `timedelta`

`_ResUsersApikeysBase._check_expiration_date` pasa de `timedelta(...)` a
`datetime.timedelta(...)`, que es la forma de la fuente
(`odoo19c: odoo/addons/base/models/res_users.py:1577-1587`, línea `:1586`).
Misma conducta; la ejercita `tests/integration/base/test_rpc_api_key_channel.py`
(`_generate` con un día de margen, usuario sin `group_system`), dentro del
subconjunto ancho de arriba.
