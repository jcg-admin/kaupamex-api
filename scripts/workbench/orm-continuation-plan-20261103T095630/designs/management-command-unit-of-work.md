# Una unidad de trabajo por orden de gestión

Creado: 2026-11-18T12:23:00 (UTC). TASK-API-0485. Sucesor de la pieza abierta de
`request-unit-of-work-integrity.md` («comandos de gestión en su unidad»).
Referencia: odoo-tools `abe4040ec1`, Odoo 19 Community.

## El contrato de la fuente

Cada orden de `odoo-bin` que lee o escribe datos abre su unidad de trabajo
explícitamente, con el cursor del registro como gestor de contexto:
`with registry.cursor() as cr:` en `odoo19c: odoo/cli/shell.py:138`,
`odoo19c: odoo/cli/populate.py:59`, `odoo19c: odoo/cli/module.py:140`,
`odoo19c: odoo/cli/obfuscate.py:172` y `odoo19c: odoo/cli/i18n.py:165`.
Al salir sin excepción, `commit()`; con excepción, `rollback()`; siempre
`close()` (`odoo19c: odoo/sql_db.py:228-245`). Lo que la orden escribe es
una transacción: o entra todo, o nada.

Dos órdenes de la fuente NO lo hacen, y por la misma razón que aquí:

- crear o borrar una base (`odoo19c: odoo/service/db.py:128-140`) corre
  en `autocommit` sobre la base `postgres`, porque `CREATE DATABASE` no
  admite transacción;
- `server` no es una unidad: sirve peticiones, y cada una abre la suya.

## Este árbol, medido

`grep -LE "transaction.atomic|registry.cursor|\.cursor\(\)"` sobre los 19
`management/commands/*.py` del producto da 14 sin unidad propia. Por orden:

| Orden | Escribe | Veredicto |
|---|---|---|
| `server` | — | fuera: sirve peticiones, cada una con `UnitOfWorkMiddleware` |
| `cron` | — | fuera: cada trabajo corre en su cursor (`registry-cursor-unit-of-work.md`) |
| `company_create`, `company_migrate_all` | DDL de bases | fuera: como `db.py` de la fuente, crear y migrar bases no es una transacción |
| `purge_logs`, `backfill_buyer_role`, `seed_rate_cards`, `auto_close_support_tickets`, `expire_vouchers`, `send_pending_emails`, `check_mp_gateway`, `mp_sandbox_charge`, `setup_mp_gateway`, `seed_l0_chart` | sí | **dentro** |

Hoy esas diez escriben en autocommit: si fallan a mitad, lo escrito queda;
lo pendiente del ORM se vuelca cuando alguien lo pida, en otra transacción,
y ninguna llama a `signal_changes()` ni a `reset_changes()`.

## Decisión

1. `orm.registry.unit_of_work(alias)`: el cuerpo transaccional que
   `UnitOfWorkMiddleware` ya tiene, sin el reintento (la fuente no
   reintenta una orden): `check_signaling()`, `transaction.atomic` +
   `transaction_scope`, volcado del ORM antes del COMMIT, y
   `signal_changes()` al salir bien o `reset_changes()` al fallar.
2. `UnitOfWorkCommand(BaseCommand)`: su `execute` corre dentro de
   `unit_of_work` sobre la base de `--database` (`default` si no la
   trae). Es el `with registry.cursor() as cr:` de la fuente, declarado en
   la clase de la orden en vez de en su cuerpo.
3. Las diez órdenes de la tabla heredan de `UnitOfWorkCommand`.

## RED (`tests/unit/base/test_management_command_unit_of_work.py`)

1. una orden que escribe y termina bien deja la fila, y `signal_changes`
   una vez;
2. una orden que escribe y lanza no deja la fila, y `reset_changes` una
   vez;
3. lo pendiente del ORM llega a la fila antes del COMMIT;
4. censo: toda orden propia que escribe hereda de `UnitOfWorkCommand`,
   salvo las cuatro excluidas por nombre con su razón.

Anulación: con `execute` sin la unidad caen exactamente 1-3.

## Ejecución (2026-11-18)

- `orm.registry.unit_of_work` ≙ `odoo19c: odoo/cli/shell.py:138` con la
  semántica de `odoo19c: odoo/sql_db.py:228`; `UnitOfWorkCommand.execute`
  en `src/addons/base/management/unit_of_work.py` la abre sobre
  `--database`.
- **Lo que la tabla no previó.** Las cinco órdenes que ya abrían
  `transaction.atomic` (`update_module_list`, `reconcile_catalog`,
  `seed_authz`, `seed_menu`, `load_sepomex`) tampoco volcaban el ORM antes
  del COMMIT ni llamaban a `signal_changes`/`reset_changes`, así que también
  heredan: son 15, no 10. Su `atomic` propio queda como savepoint.
- **Lo que un consumidor destapó.** `update_module_list` rechazaba una base
  desconocida dentro de `handle`; la unidad intentaba abrir ese alias antes
  y fallaba con `ConnectionDoesNotExist`. El rechazo, con el mismo mensaje,
  pasó a `UnitOfWorkCommand.execute`, antes de abrir nada.
- Pruebas: `tests/unit/base/test_management_command_unit_of_work.py`
  (`test_a_command_that_ends_well_commits_and_signals`,
  `test_a_command_that_raises_rolls_back_and_resets`,
  `test_pending_orm_work_reaches_the_row_before_commit`,
  `test_every_own_command_runs_in_a_unit_of_work`,
  `test_the_commands_left_outside_are_plain_commands`).
- Anulación: con `execute` sin la unidad caen exactamente las tres de
  conducta (3 de 5); el censo y las exclusiones no dependen de ella.
- Consumidores derivados (pruebas que nombran alguna de las 15 órdenes o
  `unit_of_work`): 305 passed.
- **Orden respecto de la frontera.** La unidad se incorporó al plan con
  `bin/local_plan incorporate` (procedencia en `plan.provenance.json`). La
  frontera canónica admitía en ese momento sólo `basemodel-adoption-0397`,
  cuyo `owned` (`src/addons`) se solapa por ruta con estas órdenes; esta
  unidad se ejecutó antes del paraguas, que es un programa de 333 modelos en
  70 apps y no una unidad atómica.
- **Desliz de proceso (2026-11-18T13:00:49).** El primer commit del código lo rehusó el
  gate de idioma (`APRO`/`SECU`, deuda heredada que el gate sólo mide en
  archivos en *staging*), y el F2 se lanzó igual, sobre el árbol sucio y con
  el nombre de la revisión del commit del plan (`8d6b7b0d`), que no
  contiene el cambio. Se detuvo y su log se borró; el F2 válido es el de
  `8b730e74`. Es la segunda vez que ocurre (la primera, en
  `record-loader-universality.md`): el lanzamiento debe ir condicionado a
  `commit=0` y árbol limpio, no a continuación del commit.
