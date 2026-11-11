# TASK-API-0516 — Calcular los calculados almacenados que añade una migración

Fecha: 2026-11-10. Referencia: odoo-tools
`abe4040ec1a45beee90fb694e4eae4453e46b389`.

## Contrato

`BaseModel._auto_init` (`odoo19c: odoo/orm/models.py:3220-3238`): por cada
campo almacenado, `field.update_db` devuelve si la columna es nueva; si lo
es y el campo es calculado, todas las filas existentes se marcan para
cómputo (`env.add_to_compute(field, records)`), *"so that computed required
fields are flushed before the NOT NULL constraint is added"*. El
`parent_path` nuevo se calcula con `_parent_store_compute` (`:3201-3204`,
`:3246-3247`).

## Estado medido

- `parent_path`: **satisfecho en la misma autoridad**. La migración que lo
  introduce lo calcula con `RunPython`
  (`src/addons/base/migrations/0100_ir_ui_menu_parent_path.py`, ≙
  `_parent_store_compute`).
- Calculados almacenados: **30** campos calculados almacenados entraron por
  `AddField` sobre tablas existentes (fuera de migraciones iniciales) y
  ninguno se calcula sobre las filas previas
  (`scratchpad/probe-addfield-computed.py`): `account` 1, `base` 2, `crm` 16,
  `sale` 6, `test_orm` 4. En una base con datos, esas columnas quedan en
  `NULL` o en el default hasta que algo vuelva a escribir la fila.

## Decisión

La autoridad del esquema son las migraciones (TASK-API-0515), así que el
cálculo es una **operación de migración**, no `_auto_init`:

- `orm.migration_operations.ComputeStoredFields(app_label, model_name,
  field_names)`: una operación sobre `RunPython` que toma la clase real del
  modelo (el cómputo necesita sus métodos; el modelo histórico no los tiene,
  igual que la fuente usa el código vigente), marca todas las filas con
  `add_to_compute` y vuelca con `flush_model(field_names)`. Reversa: no-op
  (los valores calculados no se deshacen).
- Toda migración que añada un calculado almacenado a una tabla existente lo
  sigue con esta operación.
- Para los 30 ya aplicados, una migración nueva por app (5) con la misma
  operación: las migraciones viejas ya corrieron en las bases desplegadas y
  editarlas no recalcula nada.

## Casos (RED)

1. Fila existente con la columna en `NULL`; la operación la deja con el
   valor de su cómputo.
2. La operación sobre una tabla vacía no falla ni consulta de más.
3. Varios campos de un mismo cómputo (`size1`, `size2`) se calculan en una
   sola pasada.
4. Guardián: una prueba recorre las migraciones y exige que cada `AddField`
   de un calculado almacenado sobre tabla existente vaya seguido de
   `ComputeStoredFields` para ese campo (o figure en la migración de
   rescate de su app).

Anulación prevista: con la operación vaciada caen 1 y 3; el guardián cae al
retirar una migración de rescate.

## Primer tramo: la operación (2026-11-10)

- RED: `ModuleNotFoundError: orm.migration_operations`.
- GREEN inicial `3 passed` **y la anulación también `3 passed`**: el control
  no discriminaba. Causa medida: la prueba leía la columna por el ORM, que
  devuelve el valor de la caché de la transacción aunque la base tenga
  `NULL` (sonda: SQL `(None, None)`, ORM `4`). Corregida a lectura por SQL,
  la operación resultó **no escribir**: el cómputo coincidía con la caché,
  nada quedaba sucio y el volcado no emitía nada. En una migración real la
  columna es nueva y la caché está vacía; la operación ahora retira de la
  caché esos campos antes de marcarlos (`_invalidate_cache`), que es el
  estado que la fuente supone.
- Tras la corrección: GREEN `3 passed`; con la operación vaciada caen
  exactamente el 1 y el 2; el 3 (tabla vacía) sobrevive, como debe.
- Pendiente en esta TASK: las 5 migraciones de rescate (`account`, `base`,
  `crm`, `sale`, `test_orm`) y el guardián de `AddField`.

## Riesgo a resolver antes de las migraciones de rescate

La operación usa la clase vigente del modelo. En una cadena de migraciones,
su cómputo puede leer columnas que migraciones posteriores de **otras** apps
aún no crearon (p. ej. `crmlead.company_id` lee de `res.partner`). La
dependencia `__latest__` no es válida: en una base desplegada, al entrar una
migración nueva en esa app, la de rescate ya aplicada quedaría con una
dependencia sin aplicar (`InconsistentMigrationHistory`). Lo que sí lo
resuelve: declarar como dependencias explícitas las hojas actuales de cada
app cuyos campos lee el cómputo, medidas con el grafo de `depends` del campo
(`registry.field_depends`). Es el siguiente paso de la TASK.

## El sitio del archivo (gate de `7ba6cd22`)

La suite integral de `7ba6cd22` dio `2 failed, 12493 passed` (más los 5
ambientales conocidos): `check_mirrored_roots` rechazó
`src/orm/migration_operations.py` por no tener contraparte de archivo en
`odoo/orm`. Se creó sin listar antes la raíz de la referencia, que es la
segunda cláusula de `atributos-de-clase-de-modelo.md`. El comportamiento sí
tiene hogar en la referencia (`BaseModel._auto_init`, dentro de
`models.py`), así que se declaró en `scripts/mirrored_roots_baseline.txt`
como *split* de `models.py`, igual que `inherits.py` (`6dad029a`), en vez
de moverlo a un sitio sin relación con su contrato.

## Segundo tramo: migraciones de rescate y guardián (2026-11-10)

- Dependencias medidas recorriendo `registry.field_depends` de cada campo
  (`scratchpad/probe-catchup-deps.py`): `account`, `base` y `test_orm` sólo
  leen su app; `crm` lee `base`, `crm` y `sales_team`; `sale` lee `account`,
  `base` y `sale`. Cada migración de rescate depende de las **hojas
  vigentes** de esas apps (ya aplicadas en una base desplegada, así que no
  hay historia inconsistente):
  `account/0031`, `base/0103`, `crm/0005` (17 campos), `sale/0015`,
  `test_orm/0042`. En una base nueva las tablas están vacías al llegar ahí y
  la operación sale sin consultar más.
- Guardián `test_new_computed_columns_are_computed.py`: RED con exactamente
  los 30 campos medidos (tras tolerar un campo de terceros —`simplejwt`—
  que una migración añade y otra retira); GREEN con las cinco migraciones;
  sin la de `crm` caen exactamente sus 17.
- Sincronía (TASK-API-0515) sigue verde: `ComputeStoredFields` es
  `RunPython` y no cambia el estado de los modelos.

## Revisión 2026-11-11: el cómputo espera a que el esquema del modelo esté completo

**Defecto medido.** Una base migrada desde cero falla en
`base/0103_compute_new_stored_columns` con
`column ir_rule.create_uid_id does not exist` (ci-multidb de `37890e41`,
`outputs/gates/ci-multidb-37890e41/`, y la reproducción en una base
desechable `orm_x2hokp_fresh`). La operación usa la clase **vigente** del
modelo, que ya declara columnas que añadirá una migración **posterior**
(`base/0109`). El `SELECT` del cómputo las nombra y la tabla aún no las tiene.
Fallaría lo mismo con cualquier campo que se añada en adelante.

**Lo que hace la fuente.** `_auto_init` (`odoo19c: odoo/orm/models.py:3170-3248`)
recorre **todos** los campos del modelo instalado. Crea todas las columnas que
faltan y sólo entonces marca para cómputo las filas existentes. En la fuente,
el esquema y el código del modelo nunca están desfasados en el momento de
calcular.

**Mecanismo.**

1. Al ejecutarse, la operación compara las columnas concretas del modelo vigente
   con las de su tabla, introspectadas por la conexión del `schema_editor`.
2. Si la tabla ya tiene todas, calcula al momento. Es la conducta anterior, y la
   que ven una base al día y la suite de la operación.
3. Si falta alguna, el cómputo queda pendiente en una cola del proceso,
   indexada por alias de base. Un receptor de `post_migrate` lo ejecuta cuando
   el `migrate` termina y todas las migraciones aplicables están aplicadas.
   El receptor se conecta antes del ciclo de instalación de módulos
   (`install_cycle.load_modules_after_migrate`), por el mismo orden de la
   fuente: primero `_auto_init` y después la carga de datos.

**Ciego a, declarado.** La cola vive en memoria del proceso de `migrate`.
Puede ocurrir que el proceso muera después de aplicar la migración que la
encola y antes de `post_migrate`. En ese caso la migración consta como
aplicada y las filas quedan sin calcular. Una base nueva no tiene filas que
perder. Una base existente con el esquema al día calcula al momento y no pasa
por la cola. El hueco queda acotado a una base vieja que además se interrumpe
a mitad del `migrate`.
Condición de cierre: persistir la cola en la propia base si un consumidor
migra bases con datos desde un esquema desfasado.
