# res.users.init — cifrar al arrancar las contraseñas en texto plano

Fecha: 2026-11-11T02:01:19. Estado: diseño, sin implementar.

## Contrato de la fuente

`odoo19c: odoo/addons/base/models/res_users.py:277-292` (odoo-tools
`abe4040ec1`): `init` selecciona las filas con `password IS NOT NULL AND
password !~ '^\$[^$]+\$[^$]+\$.'` —las que no tienen forma de MCF
extendido— y reasigna cada una a `password`, cuyo *inverse*
(`_set_password`, `:294-297`) la cifra con `_crypt_context()`. Permite
escribir una contraseña en claro por SQL y que quede cifrada al arrancar.

## Lo que el stack ya trae (TRAE)

- `ResUsers._crypt_context()` (`src/addons/base/models/res_users.py:1194`):
  el mismo contexto passlib, MCF `$pbkdf2-sha512$…` (133 caracteres).
- `set_password` cifra con ese contexto; `_set_encrypted_password`
  afirma `identify(pw) != 'plaintext'`.
- `init(cls, using=None)` lo llama `orm.registry.init_models` por base.

## Divergencia que obliga a desviarse del porte literal

Aquí «sin credencial» no es `NULL`: `set_password(None)` llama a
`set_unusable_password`, que guarda `hashers.make_password(None)` = `!` +
40 caracteres aleatorios. Ese valor **no** cumple el regex de la fuente, así
que un porte literal lo cifraría como si fuera una contraseña en claro:

- la cuenta pasaría de «no puede entrar» a «entra con la cadena `!…`»;
- `has_usable_password()` pasaría de `False` a `True`.

Es una pérdida de seguridad, no una diferencia cosmética. El filtro excluye
además `password LIKE '!%'` (el prefijo `UNUSABLE_PASSWORD_PREFIX` de
Django, leído del módulo, no transcrito) y la cadena vacía.

*Métrica:* el regex de la fuente aplicado a `make_password(None)`.
*Ciega a:* otros formatos de hash heredados de Django
(`pbkdf2_sha256$…`, sin `$` inicial) que pudieran existir en filas
anteriores al contexto passlib: el regex también los trataría como texto
plano. Medir antes de implementar cuántas filas de la base de QA y de los
seeds tienen esa forma; si hay alguna, la decisión de cómo tratarlas
(re-cifrar no es posible sin la contraseña) es del ejecutor.

## Pruebas (TDD) previstas

1. Una fila con contraseña en claro escrita por SQL queda cifrada en MCF y
   `check_password` la acepta.
2. Una fila ya cifrada no cambia (byte a byte).
3. Una fila con `set_unusable_password` no cambia y sigue sin credencial
   usable — el caso de la divergencia.
4. `NULL` y cadena vacía no cambian.
5. `init_models(['res.users'])` ejecuta el paso 1.

Controles: sin la exclusión de `!` cae exactamente la 3; sin el filtro MCF
cae la 2.

## Medición de la incógnita (2026-11-11T02:01:54)

Formas de `password` en `res_users` de la base de pruebas
(`orm_x2hokp_qa`, `NAME` y `TEST.NAME` coinciden en esta VM), por
consulta clasificadora (null / vacía / `!` / MCF / otra):

    orm_x2hokp_qa res_users [('unusable', 1)]

La única fila es la del superusuario que siembra `base/0106`
(`base.user_root`, sin credencial). Un porte literal de `init` cifraría su
marcador `!…` y dejaría al **superusuario con una contraseña conocida**.
La exclusión del prefijo `!` no es una precaución teórica: protege la
única fila que existe. Formas heredadas de Django (`otra:pbkdf2_sha256`):
0 aquí.

*Métrica:* filas de `res_users` clasificadas por la forma del valor.
*Ciega a:* bases de producción o de otros entornos, que esta VM no ve; la
cifra no se extrapola. Antes de desplegar, la misma consulta sobre cada base
destino.

## Divergencia de esquema encontrada al escribir el RED

La fuente declara `password = fields.Char(...)` sin `required`, y su `init`
filtra `password IS NOT NULL`. Aquí la columna es `NOT NULL` (medido: un
`UPDATE ... SET password = NULL` da `IntegrityError: null value in column
"password" ... violates not-null constraint`). La prueba 4 queda en la
cadena vacía; `NULL` no es alcanzable. La nulabilidad de la columna es otra
obligación de esquema (migración), fuera de esta unidad; se registra aquí
para que no se pierda.

## Resultado de la implementación (2026-11-11T02:05:26, sin commitear)

- `ResUsers.init(cls, using=None)` con `_MCF_PATTERN` (el regex de la
  fuente, `:287`) y las dos exclusiones de la divergencia (vacía, `!`).
- `_set_encrypted_password` gana `using=None` opcional: sin él, el router
  decide como antes; `init` lo pasa porque corre por base.
- `tests/unit/base/test_res_users_init.py`: RED (3 fallos: claro sin
  cifrar, `init_models`, y el `None` por la columna `NOT NULL`) → la
  prueba 4 se ajustó a la cadena vacía → GREEN 5/5.

| Mutación | Cae |
|---|---|
| retirar la exclusión del prefijo `!` | exactamente `test_an_unusable_password_stays_unusable` |
| retirar el filtro MCF | exactamente `test_an_encrypted_password_is_left_byte_for_byte` |
| retirar la exclusión de la vacía | exactamente `test_an_empty_password_is_left_alone` |

La llamada desde `init_models` ya está discriminada por el control D de
`paperformat-company-init.md` (misma línea del registro).

*Métrica:* aserciones de la suite de la unidad con cada mutación.
*Ciega a:* la llamada sobre una base no por defecto desde `init_models`
(patrón multidb), y a hashes de otros esquemas que el contexto passlib
reconozca sin forma MCF — 0 medidos aquí.

## Corrección por la admisión de estilo (2026-11-11T02:12:01)

La primera versión añadía un import de nivel módulo
(`DEFAULT_DB_ALIAS`), insertaba `init` a mitad de la clase y cambiaba la
firma de `_set_encrypted_password`. La admisión incremental
(`scripts/check_python_style_increment.py`) huella cada violación heredada
por su contexto sintáctico, que incluye la **posición** del statement en su
contenedor y la cabecera del padre (`syntax_context`, `:144-186`). Los
tres cambios desplazaban esas posiciones: 80 violaciones preexistentes de
`res_users.py` salieron como introducidas (`invalidated_context`).

Forma final, sin desplazar nada:

- `init` y `_MCF_PATTERN` al **final** del cuerpo de `ResUsers`;
- sin import nuevo: `cls.objects.db_manager(using)` (`None` deja decidir
  al router);
- `_set_encrypted_password` **intacto**: `init` escribe con
  `manager.filter(pk=uid).update(password=context.hash(raw))`. La
  precondición del método (no texto plano) se cumple por construcción.

Admisión: PASS. Los tres controles se repitieron sobre la forma final y cada
uno tumba exactamente su caso (mismos resultados que la tabla anterior). La
mención a `using` en `_set_encrypted_password` de la sección previa queda
superada por ésta.
