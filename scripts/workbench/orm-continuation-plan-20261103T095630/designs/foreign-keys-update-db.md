# Unidad FK: `Many2one.update_db_foreign_key` y `Many2many.update_db_foreign_keys`

Diseño medido el 2026-11-10T23:49:13 sobre `3d7faad3`, contra `odoo19c` (odoo-tools
`abe4040ec1`). Seleccionada como la siguiente unidad del núcleo: está en la
frontera `absent` del inventario (`src/orm/fields_relational.py`, 2 de los
7 ausentes del archivo) y es la continuación directa del contrato de
esquema s1–s5.

## Flujo ejecutable de la fuente

1. `init_models` → `model._auto_init()` → por cada columna,
   `Field.update_db` → `update_db_column`.
2. `Many2one.update_db_column` (`fields_relational.py:302-304`) encola
   `post_init(self.update_db_foreign_key, model, column)`.
3. `update_db_foreign_key` (`:306-320`) **no** escribe: declara la FK
   esperada con `registry.add_foreign_key(table, name, comodel._table, 'id',
   ondelete or 'set null', model, module)`. Sale sin declarar nada si el
   campo es `company_dependent`, si alguna de las dos tablas no es ordinaria
   (vista o `_table_query`), si el comodelo no es `_auto` o si es
   `ir_actions`.
4. `Many2many.update_db` (`:1329-1354`) crea la tabla de relación si falta
   y encola `update_db_foreign_keys` (`:1356-1367`): `column1` → tabla
   del modelo con `cascade` y `force=False`; `column2` → tabla del
   comodelo con `self.ondelete`.
5. Al final de `init_models`, `check_foreign_keys` (`registry.py:907-943`)
   crea la FK ausente, **retira y rehace** la que difiere en destino o en
   `confdeltype`, y refleja cada una en `ir.model.constraint`.

## Llamadores y consumidores aquí

- `Registry.add_foreign_key` y `Registry.check_foreign_keys` están
  portados (`src/orm/registry.py:2854-2913`); `init_models` ya llama a
  `check_foreign_keys`.
- **Nadie llena `_foreign_keys`:** 0 llamadas a `add_foreign_key` en
  `src/` y `addons/` fuera de su definición. Hoy `check_foreign_keys`
  sale siempre por `if not self._foreign_keys`.
- No hay `update_db`/`update_db_column`: las columnas las crea la
  migración. El punto equivalente a la fuente es `_auto_init` (s1–s4).

## Capacidades del stack (medidas)

| Pieza | Estado |
|---|---|
| FK reales en la base (`orm_x2hokp_qa`) | **1089**, todas `confdeltype = 'a'` (`NO ACTION`), `DEFERRABLE INITIALLY DEFERRED`: las crea Django desde la migración |
| política de borrado | la aplica Django en Python (`Collector`); `Many2one(ondelete=…)` se traduce a `on_delete` (`_apply_ondelete`, `fields_relational.py:1188`) |
| borrado en la base en Django | **no existe en 6.0.5** (`django.db.models.deletion` sólo trae `CASCADE`, `PROTECT`, `RESTRICT`, `SET`, `SET_DEFAULT`, `SET_NULL` y `DO_NOTHING`) |
| `tools.sql`: `add_foreign_key`, `get_foreign_keys`, `drop_constraint`, `_CONFDELTYPES` | portados (`src/tools/sql.py`) |

**TRAE:** el registro de FK esperadas, su verificación contra
`pg_constraint` y las primitivas SQL. **CONSTRUYE:** los dos productores, y
su llamada desde la conciliación.

## El conflicto de autoridad

Si los productores declaran el `ondelete` de la fuente y
`check_foreign_keys` se aplica tal cual, retira y rehace **las 1089 FK** de
Django, porque todas difieren en `confdeltype` (`a` frente a `c`, `n` o
`r`). Eso cambia la semántica del árbol entero:

- la FK deja de ser diferible, y con ello la carga de fixtures y el orden de
  inserción dentro de una transacción;
- el borrado pasaría a ejecutarse dos veces: en la base y en el `Collector`.

Choca con la regla ya fijada para s2 en
`schema-and-translation-symbols-decision.md` («Autoridad del esquema»):
la migración gobierna y una definición distinta **se informa, no se
recrea**.

## Opciones

| Opción | Qué hace | Coste |
|---|---|---|
| A | productores fieles; `check_foreign_keys` crea sólo la FK **ausente** y **informa** la que difiere | ninguna FK de Django cambia; se pierde el `ON DELETE` de la base que la fuente sí tiene |
| B | productores fieles; `check_foreign_keys` tal cual | reescribe 1089 FK y la semántica diferible; doble borrado |
| C | esperar a Django 6.1 (`on_delete=DB_CASCADE`…) y llevar el `ondelete` a la migración | la autoridad sigue en la migración y la base tiene el `ON DELETE`; depende de una versión no instalada |

**Recomendación preliminar: A**, porque cumple la regla de autoridad que ya
gobierna s1–s5. Es la misma divergencia que `Constraint.apply_to_database`:
el `confdeltype` distinto se registra con su motivo. La elección entre A y C
es decisión del ejecutor: cambia la semántica de borrado en la base, y lo
arquitectónico no se deriva.

## Pruebas previstas (RED primero)

1. `update_db_foreign_key` declara `(tabla, columna) → (comodelo, 'id',
   ondelete)` en `_foreign_keys`.
2. No declara nada para `company_dependent`, para una vista o para un
   comodelo no administrado.
3. `update_db_foreign_keys`: `column1` con `cascade` y `force=False`
   (no pisa una declaración previa); `column2` con el `ondelete` del campo.
4. Con la opción A: una FK ausente se crea y se refleja; una FK de Django con
   otro `confdeltype` queda intacta y se informa.
5. Controles: sin la llamada desde la conciliación, `_foreign_keys` queda
   vacío; sin la guarda de vistas, se declara una FK sobre una vista.

## Barrido de obligaciones del archivo

Los otros 5 ausentes de `src/orm/fields_relational.py` son `_Relational`
y sus atributos (`check_company`, `context`, `domain`, `relational`): es
la jerarquía de clases de campos, ligada a la frontera de `BaseString`/
`Id`/`BaseDate`, y **no** entra en esta unidad.

## Resultado del primer tramo (2026-11-10T23:53:52)

Implementados los dos productores, **sin conectar**:

- `models.ForeignKey.update_db_foreign_key` y
  `Many2manyField.update_db_foreign_keys` (`src/orm/fields_relational.py`),
  por la misma vía de instalación que el resto de métodos de la fuente sobre
  `ForeignKey`. El registro se resuelve por el alias activo
  (`get_current_cr()`), igual que `_auto_init`.
- Pruebas `tests/unit/orm/test_foreign_key_producers.py`: 5 casos (puntos
  1–3 del plan de pruebas). Rojo inicial por `AttributeError`; verde 5/5.
- Anulación: sin la guarda de comodelo no administrado cae exactamente
  `test_many2one_declares_nothing_towards_an_unmanaged_comodel`; sin
  `force=False` cae exactamente
  `test_many2many_column1_does_not_override_a_previous_declaration`.

**Sin conectar a propósito:** llamar a los productores desde `_auto_init`
con el `check_foreign_keys` actual reescribiría las 1089 FK de Django
(opción B). La conexión, con los puntos 4 y 5 del plan, espera la decisión
entre A y C.
