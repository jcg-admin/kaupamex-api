# Contrato de borrado: Odoo 19, Django 6.0.5 y Django 6.1.3

Investigación medida el 2026-11-11T00:13:06 sobre `3d7faad3` (código) y `3bc89db1`
(diseño previo), contra `odoo19c` (odoo-tools `abe4040ec1`), Django 6.0.5
instalado y Django 6.1.3 descargado sin instalar
(`django-6.1.3-py3-none-any.whl`, extraído aparte en el scratchpad).
Continúa `foreign-keys-update-db.md`. Corrige su premisa «esperar a Django
6.1»: 6.1 se publicó el 2026-08-05 y su última versión es 6.1.3.

Evidencia ejecutable, fuera del árbol del producto:
`probes/delete_paths.py` (transacción revertida, salida en `outputs/delete_paths.out`) y `probes/fk_census.py` (salida en `outputs/fk_census.out`)
(solo lectura), ambos marcados EXPERIMENTAL.

## 1. Contrato de la fuente

| Pieza | Fuente | Qué hace |
|---|---|---|
| `Field.update_db_column` → `Many2one.update_db_column` | `fields_relational.py:302-304` | encola `update_db_foreign_key` en `post_init` |
| `Many2one.update_db_foreign_key` | `:306-320` | declara `(tabla, columna) → (comodelo, 'id', ondelete or 'set null')`; sale si es `company_dependent`, si una tabla no es ordinaria, si el comodelo no es `_auto` o es `ir_actions` |
| `Many2many.update_db` / `update_db_foreign_keys` | `:1329-1367` | crea la tabla de relación si falta; `column1` → modelo con `cascade` y `force=False`; `column2` → comodelo con `self.ondelete` |
| `Registry.add_foreign_key` | `registry.py:894-905` | `force` decide si pisa |
| `Registry.check_foreign_keys` | `:907-943` | crea la ausente; **retira y rehace** la que difiere en destino o `confdeltype`; refleja en `ir.model.constraint` |
| `tools.sql.add_foreign_key` | `tools/sql.py:475-484` | `ALTER TABLE … ADD FOREIGN KEY … ON DELETE <ondelete>`: **no diferible** |
| `BaseModel.unlink` | `models.py` | métodos `@api.ondelete` del propio modelo, `flush_all`, `modified(before=True)` y `DELETE` por SQL; la cascada, el `SET NULL` y el `RESTRICT` los ejecuta PostgreSQL, y **los hijos borrados en cascada no pasan por su `unlink`** ni por sus `@api.ondelete` |
| alias | — | el `cr` del `Environment` de la base que se instala |
| transacción | — | la del ciclo de carga del módulo; un error aborta el paso |

## 2. Lo que el stack hace hoy (medido)

**Censo** (`probes/fk_census.py`, modelos administrados, `db_constraint`):
911 FK de modelos, más 89 Many2many automáticos con 2 FK cada uno: 911 +
178 = **1089**, la cifra de `pg_constraint`. Todas son `NO ACTION` y
`DEFERRABLE INITIALLY DEFERRED`.

| `on_delete` de Django | FK |
|---|---|
| `SET_NULL` | 392 |
| `CASCADE` | 384 |
| `PROTECT` | 128 |
| `RESTRICT` | 7 |

**Borrado medido** (`probes/delete_paths.py`):

| # | Camino | Resultado |
|---|---|---|
| 1 | `unlink` del ORM sobre un `CASCADE` de Django | el hijo se borra; `pre_delete` se emite **también para el hijo** (2 señales) |
| 2 | `DELETE` SQL con `ON DELETE CASCADE` | el hijo se borra sin pasar por Python |
| 3 | `DELETE` SQL contra una FK diferida de Django | aceptado en el acto; la violación salta sólo al comprobar las restricciones (`IntegrityError` al forzar `SET CONSTRAINTS ALL IMMEDIATE`) |
| 4 | `ON DELETE RESTRICT` no diferible | error inmediato |

## 3. Django 6.1.3 (leído del paquete, sin instalar)

- `DB_CASCADE`, `DB_SET_NULL` y `DB_SET_DEFAULT` son `DatabaseOnDelete`
  (`deletion.py:84-103`). Están en `SKIP_COLLECTION`: el `Collector` no
  recoge esas filas y no emite señales para ellas. `DB_CASCADE` lleva
  `forced_collector=CASCADE`, que sólo se usa con `force_collection`.
- La FK se crea con `ON DELETE <op>` **y sigue siendo `DEFERRABLE INITIALLY
  DEFERRED`** (`base/schema.py:125-127`, `:1830`).
- No hay `DB_RESTRICT`.
- Comprobaciones del sistema: `E320` (`DB_SET_NULL` sin `null=True`),
  `E322` (`DB_SET_DEFAULT` sin `db_default`), `E324` (motor sin soporte)
  y **`E323`: no se pueden mezclar variantes de base y de Python en una
  misma cadena de referencias** (`fields/related.py:1137-1166`).
- Compatibilidad: requiere Python ≥ 3.12 (aquí 3.13). DRF 3.16.1,
  simplejwt 5.5.1, drf-spectacular 0.29.0 y django-cors-headers 4.9.0
  declaran `django>=4.2` sin tope; sus clasificadores llegan a 5.2 o 6.0,
  así que 6.1 está **sin declarar ni probar** por ellos.
- `pyproject.toml` fija `Django==6.0.5`. **No se actualiza** en este pase.

## 4. Comparación contractual

| `ondelete` de la fuente | Odoo (PostgreSQL) | Django 6.0.5 hoy | Django 6.1.3 |
|---|---|---|---|
| `cascade` | `ON DELETE CASCADE` inmediato; el hijo no ejecuta su `unlink` | `CASCADE` en Python: el hijo **sí** emite señales y corre sus comprobaciones de borrado; un `DELETE` por SQL deja la FK violada hasta el commit | `DB_CASCADE`: igual que Odoo en la cascada; la FK sigue diferida |
| `set null` | `ON DELETE SET NULL` inmediato | `SET_NULL` en Python | `DB_SET_NULL`, exige `null=True` |
| `restrict` | `ON DELETE RESTRICT`: error inmediato | `PROTECT`/`RESTRICT` en Python: error inmediato en `unlink`; un `DELETE` por SQL falla sólo al commit | sin `DB_RESTRICT`: queda en Python |
| Many2many | `column1` `cascade`; `column2` `ondelete` del campo | borrado rápido de la tabla intermedia por el `Collector` | igual que hoy (la tabla automática no admite `on_delete`) |
| `company_dependent` | sin FK (jsonb) | sin FK | sin FK |

`CASCADE` y `DB_CASCADE` **no son equivalentes**: el primero ejecuta
señales y comprobaciones en los hijos y el segundo no. La fuente se parece al
segundo.

## 5. Determinación

1. **Se conservan las 1089 FK como restricción de integridad.** Garantizan
   que no quede una referencia huérfana al commit, que es lo que la
   restricción de la fuente también garantiza. No se reescribe ninguna.
2. **La acción de borrado necesita otra implementación donde la fuente
   declara `cascade` o `set null`.** La equivalente es `DB_CASCADE` o
   `DB_SET_NULL`, que exigen Django 6.1 y cumplir `E323` en toda la cadena
   de referencias de cada modelo. Es una unidad propia, con la actualización
   de Django como dependencia, y no se aplica parcialmente.
3. **`restrict` se queda en Python** (`PROTECT`/`RESTRICT`): sin
   `DB_RESTRICT` en ninguna versión, es el mecanismo del stack con el mismo
   efecto visible (error inmediato en `unlink`).
4. **Política provisional, no destructiva, para `check_foreign_keys`**:
   detectar, comparar y registrar. Una FK existente que difiere no se toca.
   Una ausente sólo se crea si **no** la gestiona Django, es decir, si
   ninguna migración la declara (tabla creada fuera del estado de
   migraciones). Esto **no** declara conforme la semántica de las FK
   existentes. Es un paso de seguridad.

## 6. Hallazgo: el atributo `ondelete` no refleja la política efectiva

Cruce del atributo `ondelete` con el `on_delete` de Django, sobre 911 FK:

| (`ondelete`, `on_delete`) | FK | Ejemplo |
|---|---|---|
| (`set null`, `SET_NULL`) | 369 | coherente |
| (`restrict`, `CASCADE`) | 181 | `base.ResUsersApikeys.user`: la fuente declara `cascade` (`res_users.py:1526`); el atributo miente |
| (`set null`, `CASCADE`) | 111 | `base.IrModuleDependency.module`: la fuente declara `cascade` (`ir_module.py:1009`); el atributo miente |
| (`-`, `CASCADE`) | 82 | modelos de Django contrib |
| (`set null`, `PROTECT`) | 68 | `base.IrModuleCategory.parent`: la fuente no declara nada, o sea `set null` (`ir_module.py:83`); la **política** se aparta |
| (`restrict`, `PROTECT`) | 49 | coherente |
| (`-`, `SET_NULL`) | 23 | contrib |
| (`-`, `PROTECT`) | 11 | — |
| (`cascade`, `CASCADE`) | 10 | coherente |
| (`set null`, `RESTRICT`) | 7 | — |

**Causa:** cuando el porte pasa `on_delete` explícito sin `ondelete`,
`_apply_ondelete` es transparente y el atributo sale después de la regla por
defecto (`restrict` si es obligatorio, `set null` si no), no de la política.
Así, `update_db_foreign_key`, que lee `self.ondelete` como la fuente,
declara una política equivocada en esos campos.

**Obligación:** el `ondelete` de cada FK debe ser el de su campo en la fuente,
y `on_delete` debe derivar de él. Es un barrido por campo contra
`odoo19c`. Hasta cerrarlo, los productores no se conectan.

## 7. Matriz de pruebas

| # | Caso | Estado |
|---|---|---|
| 1 | FK ausente | pendiente: depende de la política provisional en `check_foreign_keys` |
| 2 | FK existente equivalente | pendiente: ídem |
| 3 | FK existente divergente: se informa y no se toca | pendiente: ídem |
| 4 | diferencias entre acciones de borrado | **medido** (`probes/delete_paths.py`, casos 1-4); falta llevarlo a la suite |
| 5 | restricción diferible | **medido** (caso 3 del probe); falta llevarlo a la suite |
| 6 | comodelo no administrado | **cubierto**: `test_many2one_declares_nothing_towards_an_unmanaged_comodel` (`bc487a66`) |
| 7 | tabla que no es ordinaria | pendiente |
| 8 | migración posterior | pendiente |
| 9 | reejecución idempotente | pendiente |
| 10 | bases independientes por alias | pendiente: va al ci-multidb |
| 11 | borrado por el ORM | **medido** (caso 1 del probe) |
| 12 | borrado por SQL directo | **medido** (casos 2-4 del probe) |

Las 5 pruebas verdes de `bc487a66` cubren los productores. **No** cubren la
familia de FK.
