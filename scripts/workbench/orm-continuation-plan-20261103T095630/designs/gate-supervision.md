# Supervisión de gates: preflight, corte en el primer fallo y timeouts

Intervención 4.3.1 §3-§5. Implementado sobre el runner existente
(`probes/gate-procedure/full-batch.sh`), sin otra arquitectura.

## Incidentes que lo motivan (2026-11-17)

| Hecho | Medición |
|---|---|
| F2 sobre `d1dd7d58`, 1ª vez | 1 857 F/E al 5 % por una base `_gw*` sin `res_users.id=1`, que dejó a medias una ejecución cortada por el límite de 600 s de la herramienta |
| reconstrucción `--create-db -n 4`, 1º intento | cortada por `timeout 1500` mientras migraba (no estaba bloqueada: actividad SQL en las cuatro bases cada minuto) |
| reanudación `--reuse-db` | 1 324 s; las migraciones continuaron donde quedaron, y 19 errores en la carga de `account_security.xml`: `commercial_partner_id` nulo |
| causa del nulo | `0116` aplazó su `ComputeStoredFields` (la `0117` añade columna a `res_partner`) en `PENDING_COMPUTES`, en memoria; el corte lo perdió. Unidad `orm-pending-computes-durable-0516` |
| reparación | `compute_now` de `0116` sobre las cuatro bases: 2 → 0 filas nulas cada una; 19/19 verde |
| F2, 2º intento | 1 fallo real (regresión propia) visto al 94 %; la suite siguió 6 minutos más hasta el resumen |

## Preflight — `scripts/gate_preflight.py`

Antes de pytest, sobre cada base que usará la ejecución (`<base>_gw<N>`):
conexión, migraciones del grafo sin aplicar, datos de referencia (usuario
`id=1` y su `commercial_partner_id`) y otro pytest vivo. Exit 0/1/2; el
gate sale con `EXIT=95` si falla. Pruebas:
`tests/unit/scripts/test_gate_preflight.py`; anulada la consulta de
referencia cae exactamente el positivo.

## Stop-on-error

`--maxfail=1`. Medido con xdist 3.6.1 y `-n 4` en una sonda de 40 casos
con un fallo en el 4º: se detiene tras 14 casos, rc=2, 3 s; los casos ya en
curso terminan (no hay corte instantáneo). `test_multidb_isolation` sale de
F2 (`--ignore`): sus 15 errores son de diseño fuera de su base desechable y
su veredicto lo da F3 (`scripts/run_multidb_isolation.py`). Dentro, el
corte saltaría siempre.

El veredicto se lee de `EXIT=` del log (el `rc` real de pytest), nunca de
`grep passed`.

## Timeouts

- **Suite y preparación no llevan un `timeout` absoluto más corto que su
  duración medida.** La preparación de cuatro bases desde cero tardó más de
  1 500 s + 1 324 s; un tope de 1 500 s la cortaba por construcción.
- La salud se juzga por progreso: actividad SQL por base (`pg_stat_activity`)
  y `wait_event`, no por el porcentaje de pytest, que no avanza mientras
  migra.
- La herramienta de primer plano corta a 600 s: nada que escriba en las
  bases `_gw*` se ejecuta en primer plano si puede pasar de ese límite; va
  a segundo plano con su log y `EXIT=`.

## Reanudación

Una preparación cortada se retoma con `--reuse-db` (cada migración es
atómica en PostgreSQL y queda en `django_migrations`), pero lo aplazado a
`post_migrate` se pierde: tras una reanudación, el preflight es obligatorio
antes de F2.

## Lo que no ve

*Métrica:* filas de referencia y migraciones del grafo por base.
*Ciega a:* otros datos sembrados por migraciones o `post_migrate` que no
estén en `REFERENCE_CHECKS`; se amplía cuando un incidente nombre otro.

## Defecto del propio detector, medido al cablearlo

`pgrep -f '[p]ytest'` contaba al shell que lanzaba el preflight, cuya línea
de comando llevaba «pytest»: el preflight se rehusaba a sí mismo. Ahora
excluye al proceso y a sus ancestros (`/proc/<pid>/stat`). Control en
`test_the_launching_shell_is_not_competition`: con la exclusión reducida
al propio pid cae exactamente ese caso (7 → 6 passed).

## Preparación separada de la verificación (2026-11-17)

El preflight rehusó la primera revisión con migraciones nuevas
(`d6ec96e9`, `purchase.0023`/`0024`): «2 migraciones sin aplicar» en las
cuatro bases. Era el caso normal, no una base dañada: con `--reuse-db`
pytest las habría aplicado. `--prepare` aplica antes las pendientes
(`migrate` por alias, con sus señales) y la verificación corre después;
sin la bandera el preflight sigue sin escribir. Prueba:
`test_preparation_migrates_only_a_database_with_pending_migrations`; con el
`migrate` anulado cae exactamente ese caso (8 → 7).

## Una base a medio resembrar pasa el preflight (2026-11-17)

Medido: la F2 de `a72e109f` falló a los 7 min en el *setup* de una prueba
de `gw1` con `Identificador externo no encontrado: base.user_root`. La
ejecución anterior se cortó por `--maxfail=1` dentro del *teardown* que
resiembra, justo entre crear la fila del usuario 1 y su XML-ID
(`src/addons/base/data/res_users_data.py:51`). Estado de las cuatro bases:

| Base | filas de `ir_model_data` | XML-ID de `base` sembrados |
|---|---|---|
| `orm_x2hokp_qa_gw0`, `gw2`, `gw3` | 1021 | `user_root`, `partner_root`, `public_user`, `public_partner`, `paperformat_euro` |
| `orm_x2hokp_qa_gw1` | 595 | ninguno de los cinco |

`REFERENCE_CHECKS` sólo miraba la fila de `res_users` y su socio, que sí
estaban: `PREFLIGHT OK`.

Cambio: `REFERENCE_CHECKS` de `scripts/gate_preflight.py` comprueba además
los XML-ID `base.user_root`, `base.public_user` y `base.paperformat_euro`,
uno por cada uno de los sembradores cuarto, quinto y sexto. Prueba:
`tests/unit/scripts/test_gate_preflight.py`, borrando la fila del XML-ID
dentro de la transacción de la prueba.

Reparación de la base: no se construye nada. Un test transaccional sobre esa
base (`DB_QA_NAME=<base>`) la vacía y la resiembra entera en su *teardown*,
que es el mecanismo de `tests/conftest.py`.

*Métrica:* presencia de tres filas de `ir_model_data`.
*Ciega a:* un corte posterior al sexto sembrador; lo cubriría comparar el
conteo de XML-ID entre bases, que queda sin construir mientras no ocurra.
