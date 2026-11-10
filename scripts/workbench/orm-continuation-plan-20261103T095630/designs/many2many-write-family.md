# La familia de escritura de `Many2many` (TASK-API-0485)

Referencia: odoo-tools `abe4040ec1`, Odoo 19 Community,
`odoo/orm/fields_relational.py`: `_RelationalMulti.write`/`write_batch`
(`:737-764`), `Many2many.write_real` (`:1413-1594`), `Many2many.write_new`
(`:1596-1640`).

Sigue a `stored-computed-one2many.md`, que portó la misma familia para
`One2many` (`api@c9c7b545`).

## Estado medido (2026-11-10)

- `Many2manyField` es un `models.ManyToManyField`: hereda `write` de
  `models.Field` (`_field_write`, `orm/fields.py:4703`), que escribe la caché
  como un escalar. La referencia despacha un x2many por `write_batch`.
- Consumidores de `field.write(...)` que alcanzan un campo cualquiera:
  `BaseModel.__setitem__` sobre filas en cómputo (`orm/models.py:9289`) y
  `FieldDescriptor.__set__` (`orm/fields.py:1943-1980`, sólo campos con ese
  descriptor; el `Many2many` usa el `ManyToManyDescriptor` de Django).
- La escritura real de hoy: `RecordLoaderMixin._pop_many2many_values` →
  `apply_many2many_commands` (`orm/commands.py:194`), por fila.
- Obligaciones `absent` del inventario: `Many2many.write_real`,
  `Many2many.write_new`, `Many2many.update_db_foreign_keys`.

## Contrato de `_RelationalMulti` (`fields_relational.py:556-840`) y su dueño aquí

19 métodos y 1 atributo. Medido sobre `c9c7b545` qué clase define cada uno
para el `One2many` declarado (O2M) y `Many2manyField` (M2M, un
`models.ManyToManyField`):

| Símbolo | O2M | M2M | Clase |
|---|---|---|---|
| `write_sequence = 20` | ausente | `0` (de `models.Field`) | divergente |
| `_update_inverse` | `One2many._update_inverse` | `_relational_multi_update_inverse` | implementado bajo otro dueño |
| `_update_cache` | protocolo de `Field` | `_relational_multi_update_cache` | ídem |
| `convert_to_cache` / `convert_to_record` / `convert_to_read` / `convert_to_export` | ausentes | los genéricos de `models.Field` | sin verificar |
| `convert_to_record_multi` | ausente | ausente | ausente |
| `convert_to_write` | ausente | `_reverse_one2many_convert_to_write` | sin verificar |
| `convert_to_display_name` | ausente | `_relational_multi_convert_to_display_name` | implementado bajo otro dueño |
| `get_depends` | ausente | genérico | sin verificar |
| `create` | ausente | `_field_create` genérico | divergente (la fuente: `write_batch(..., True)`) |
| `write` / `write_batch` | métodos de `One2many` (`c9c7b545`) | `_field_write`, escalar | M2M divergente |
| `write_real` / `write_new` | métodos de `One2many` | ausentes | M2M ausente |
| `_check_sudo_commands` | `orm.commands._check_sudo_commands` (gestor de contexto) | ídem | implementado bajo otro dueño, firma distinta |
| `condition_to_sql`, `_get_query_for_condition_value`, `_condition_to_sql_relational` | `_multi_*`/`_one2many_*` | `_multi_*`/`_many2many_*` | implementados |

**El componente común ya existe**: funciones de módulo `_relational_multi_*`
instaladas sobre sus dueños efectivos (`models.ManyToManyField`,
`models.ManyToOneRel` y el `One2many` declarado). Es la forma que el árbol
dio a `_RelationalMulti`, porque los dos primeros son clases de Django. La
decisión TRAE: los métodos compartidos de la referencia se escriben UNA vez
como `_relational_multi_<método>` y se instalan en los dueños, en lugar de
quedar como métodos de `One2many`. Lo específico de tipo
(`write_real`/`write_new`) vive en su dueño.

## Unidad

- `_relational_multi_write`, `_relational_multi_write_batch`,
  `_relational_multi_create`, `_relational_multi_convert_to_record_multi` y
  `write_sequence = 20`, instalados en `One2many` y `ManyToManyField`
  (`write`/`write_batch` salen de la clase `One2many`).
- `Many2many.write_real` (`:1413-1594`) sobre `apply_many2many_commands`, por
  registro; `Many2many.write_new` (`:1596-1700`), con su cálculo de la
  relación vieja y nueva y la caché del inverso.
- Modelo de la referencia: `test_orm.compute.onchange` y su línea
  (`test_orm.py:880-950`), con `line_ids` (`One2many` calculado almacenado) y
  `tag_ids` (`Many2many` calculado almacenado sobre `test_orm.multi.tag`).
- Pruebas: `test_create`, `test_copy`, `test_write`, `test_set`,
  `test_set_new` (`test_onchange.py:958-1120`), los atributos de
  `test_fields.py:114-131`, y el RED de `__setitem__` sobre una fila en
  cómputo con `tag_ids`. `test_copy_batch` necesita `test_orm.partner`:
  pendiente.

## Gate y emplazamiento

Worktree en la forma cualificada (`verification-and-publication-operations.md`):
`$S/gate-<rev>/kaupamex-api`, `src/.env` y `.env` copiados,
`THYROX_ROOT=/home/user/thyrox THYROX_CLONE_PREFIX=kaupamex-`. Medido sobre
`c9c7b545` en esa forma: `test_check_workbench.py` 20 passed, que confirma la
causa de los 2 fallos del gate del worktree anterior.

## Implementación (worktree sobre `c9c7b545`)

- **Lectura del `Many2many`** (`_x2many_descriptor_get`): el lado directo de
  un campo almacenado pendiente se recalcula antes de leer (≙
  `Field.__get__`, `:1754-1790`); un dueño `NewId` lee la caché del campo
  (`transaction.field_data`), no la tabla.
- **Asignación** (`_many2many_descriptor_set`, el existente, extendido): las
  dos ramas de `Field.__set__` para un `BaseModel` — fila protegida →
  `field.write` sin lógica de negocio (`:1820-1823`); `NewId` →
  `protecting` + `modified(before)` + `field.write` + `modified`
  (`:1825-1832`). En la fila guardada, un recordset se convierte en
  `Command.set` antes de `write` (≙ `convert_to_write`), lo que evita la
  recursión.
- **`ManyToManyRel`** recibe `_update_inverse`, `_get_cache` y
  `_update_cache` del componente común, porque `write_new` actualiza la caché
  del inverso.
- **`convert_to_cache` del `Many2many`**: la rama de `_RelationalMulti`
  sólo cuando el comodelo es `BaseModel` (`_from_ids`). Para un comodelo de
  Django (`res.groups`, `res.users`) se conserva el valor anterior.
- **`write` con comodelo de Django**: `_relational_multi_write` cae a
  `models.Field.write`. **Divergencia declarada**: la referencia no tiene
  comodelos que no sean `BaseModel`; aquí los grupos y los usuarios son
  modelos de Django y no admiten `_from_ids`. Sin esta rama la regresión del
  subconjunto daba 227 fallos y 242 errores.
- **`write_batch`** acepta el `QuerySet` del comodelo como conjunto de filas
  (el papel del recordset de `:744`).
- **Anuncio único de `write`** (TASK-API-0511, `write-announces-computed.md`):
  `RecordLoaderMixin.write` anuncia `modified(vals)` de los campos declarados
  al final (≙ `:4486`), en lugar de anunciar sólo los silenciados. El
  descriptor de un campo ordinario deja de anunciar cuando `WRITING_VALUES`
  está activo, para que cada campo se anuncie una vez.

## Evidencia

- RED medido sobre `c9c7b545` con sólo el modelo, la migración y la prueba
  (worktree aparte, sin la implementación): 7 failed, 4 passed — `test_copy`,
  `test_write`, `test_setitem_on_a_record_being_computed_writes_the_relation`,
  `test_many2many_write_family`, `test_many2many_write_new_stays_in_cache`,
  `test_many2many_write_batch_accepts_the_comodel_queryset` y
  `test_protected_assignment_skips_the_model_write`. Los 4 que pasaban
  (`test_stored_editable_computed_field_attributes`, `test_create`,
  `test_set`, `test_set_new`) dependen del One2many de `c9c7b545`.
- GREEN: `test_compute_onchange.py` 11 passed.
- Regresión del subconjunto (`test_orm`, `unit/orm`, `integration/base`,
  `unit/base`, `unit/hr_skills`, `integration/sale`, `unit/stock`): 6473
  passed, 0 fallos, 6 xfailed.
- Controles de anulación sobre `test_compute_onchange.py`,
  `test_write_announces_computed.py` y `test_res_currency_round.py`:

| Anulación | Caen |
|---|---|
| familia común sin `ManyToManyField` | 4 |
| `write_real` almacenado sin tabla intermedia | 3 |
| `write_new` sin `NewId` | 1 |
| `write_batch` sin la rama `QuerySet` | 1 (`test_many2many_write_batch_accepts_the_comodel_queryset`) |
| `convert_to_cache` sin la rama `BaseModel` | 1 |
| lectura sin `recompute` | 1 (`test_copy`) |
| lectura de `new()` sin caché | 1 |
| `write` sin `modified(vals)` final | 4 |
| el descriptor anuncia dentro de `write` | 1 (`test_an_ordinary_field_is_announced_once`) |
| descriptor sin la rama protegida | 1 (`test_protected_assignment_skips_the_model_write`) |

  Las dos anulaciones de `QuerySet` y de la rama protegida no hacían caer
  nada en la primera ejecución; cada una reveló una prueba que faltaba, y las
  dos se añadieron.

- Gate completo en el worktree cualificado (`$S/gate-m2m/kaupamex-api`, base
  `c9c7b545`, `THYROX_ROOT=/home/user/thyrox THYROX_CLONE_PREFIX=kaupamex-`,
  `pytest -n 4 -q --reuse-db -p no:randomly`): **12 581 passed, 66 skipped,
  6 xfailed, 0 failed, 5 errors** en 529 s. Los 5 errores son
  `test_multidb_isolation.py` con `RuntimeError: Isolation fixture requires
  an explicitly owned disposable default`: exigen la base desechable de
  `make ci-multidb`, que se ejecuta aparte sobre la revisión publicada.
  `test_check_workbench` no falla en la forma cualificada.
- Hashes sha256 (prefijo) de los archivos copiados al árbol principal,
  iguales al worktree: `fields.py` `af938276ecfc`, `fields_relational.py`
  `2ae8de7f049b`, `models.py` `4bf6fe00af41`, `test_orm.py`
  `8149ce35f863`, `0044_compute_onchange.py` `621f4bd4aca7`,
  `test_compute_onchange.py` `a4328b361363`.
- Tras el gate, la admisión de estilo exigió partir líneas que ya existían y
  cambiaron de posición, quitar una línea en blanco de `models.py` y partir
  el `db_table` de la migración. Nuevos hashes: `fields_relational.py`
  `91571d166a67`, `models.py` `c1756ce3f935`, `0044_compute_onchange.py`
  `079ea99577ac`. Equivalencia: `ast.dump` igual sin docstrings en
  `models.py`; en `fields_relational.py` igual tras aplicar a la copia previa
  las dos reescrituras semánticas que la admisión pide (E731: el `lambda`
  `browse` pasa a `def`; `get_origin` pasa de expresión condicional a `if`).

## El gate de atributos de clase

`write_sequence = 20` en `ManyToManyField` salda la fila congelada
`write_sequence::ManyToManyField::Many2many(hereda _RelationalMulti)` de
`scripts/field_class_attributes_baseline.txt`, que se retira. Al hacerlo,
`check_field_class_attributes.py` publicaba un incumplidor nuevo: comparaba
`ManyToManyField` también contra `_Relational` (`REFERENCE_CLASS_TO_DJANGO`
lo mapea a los dos), que hereda el 0 de `Field`. El gate gana
`more_specific_owner`: una clase de Django se mide contra la clase más
específica de la fuente que la mapea, no contra su ancestro. Pares medidos:
297 → 254 (los 43 que salen son `_Relational` sobre `ForeignKey` y
`ManyToManyField`, medidos ya bajo `Many2one` y `Many2many`). Control:
devolver `write_sequence` a 0 hace caer exactamente
`write_sequence ManyToManyField … Many2many hereda _RelationalMulti=20`.
La admisión de estilo pidió además retirar el `key = lambda row: row  # noqa:
E731` del gate (la identidad: `sorted(..., key=key)` es `sorted(...)`) y
partir líneas desplazadas; la salida del gate es idéntica antes y después
(`diff` vacío) y su suite `test_field_class_attributes.py` da 15 passed.

## Inventario tras la unidad (`8f4cd889`)

`inventory_by_kind.py` sobre `src/orm` y `src/tools`: 2512 aplicables, 969
satisfechos, **365** ausentes, 0 divergentes, 1178 sin verificar. Frente a
`c9c7b545` cambia una fila: `_RelationalMulti.write_batch` pasa de
`not_verified` a `absent`. Es una **ceguera del instrumento**, no una
ausencia: el censo marca `absent` cuando ningún `def write_batch` se declara
en el árbol, y la unidad sacó el método de la clase `One2many` para
instalarlo con `setattr` desde `_relational_multi_write_batch`. Medido:
`One2many.write_batch.__name__` y `ManyToManyField.write_batch.__name__` son
`_relational_multi_write_batch`. Corregirlo exige que el censo reconozca las
instalaciones por `setattr` sobre un dueño mapeado; queda registrado aquí y
no se cuenta como progreso ni como retroceso.

## Representación explícita de `_RelationalMulti` (diseño, 2026-11-10)

**Por qué hoy se instala con `setattr`.** Los dueños efectivos del contrato
son, en parte, clases de Django (`models.ManyToManyField`, `ManyToOneRel`,
`ManyToManyRel`) cuyas jerarquías no son nuestras: no se puede insertar una
base en su MRO sin reemplazar la clase de Django. Por eso cada método
compartido es una función de módulo `_relational_multi_<método>` asignada a
cada dueño. Funciona, pero el contrato no existe como **símbolo**: el
inventario marca `_RelationalMulti` (clase) y `write_batch` como `absent`
aunque la conducta esté verificada.

**Decisión.** `class _RelationalMulti` se declara en `fields_relational.py`
con los métodos compartidos bajo sus nombres de la fuente (`write`,
`write_batch`, `create`, `convert_to_record_multi`, `_update_inverse`,
`_update_cache`, `convert_to_cache`, `convert_to_display_name`,
`write_sequence = 20`), cuerpos movidos de las funciones de módulo sin
cambiarlos. `One2many` —nuestra— hereda de ella. A los dueños de Django se
les instalan sus métodos con un único instalador que los lee del
`__dict__` de la clase (sin una segunda lista de nombres); lo específico de
tipo (`write_real`/`write_new` de `Many2many`) sigue en su dueño. No cambia la
conducta: los mismos objetos función acaban en los mismos dueños.

**Inventario.** `inventory_by_kind.py` gana una columna por fila que
distingue símbolo de la referencia, símbolo **declarado** (AST), símbolo
**instalado en tiempo de ejecución** (el atributo existe en la clase dueña
tras `django.setup()`, y de qué función procede) y verificación por conducta
(prueba que lo ejercita). Ningún símbolo pasa a `satisfied` sólo por estar
instalado; `absent` deja de usarse para uno instalado y verificado.

**Pruebas.** `ManyToManyField.write_batch is
_RelationalMulti.__dict__['write_batch']` (y para cada método compartido y
cada dueño de Django); `issubclass(One2many, _RelationalMulti)`; las suites
existentes de escritura relacional sin cambios. Control: retirar un nombre de
la clase hace caer la prueba de su instalación en cada dueño.

## `_RelationalMulti` explícita — implementación

Alcance de esta unidad: lo que el bucle de instalación ponía en los dos
dueños (`write`, `write_batch`, `create`, `convert_to_record_multi`,
`write_sequence = 20`). Los demás miembros compartidos
(`_update_inverse`, `_update_cache`, `convert_to_cache`,
`convert_to_display_name`) se instalan hoy con envoltorios distintos por
dueño (`_reverse_one2many_only`, propiedades sobre `ManyToOneRel`) y quedan
para su propia unidad.

- `class _RelationalMulti` declarada al final del módulo; los cuatro métodos
  se movieron de funciones de módulo a métodos sin cambiar firma ni cuerpo
  (comparado por AST, docstrings normalizados con `inspect.cleandoc`: iguales
  en los cuatro).
- Los dos dueños, `One2many` y `models.ManyToManyField`, reciben los miembros
  leídos de `vars(_RelationalMulti)` (sin una segunda lista).
- **Pendiente declarado: que `One2many` herede de `_RelationalMulti`**, como
  en la fuente. Se implementó así primero y el gate completo pasó (12 602
  passed, 0 failed), pero cambiar la cabecera de `One2many` cambia el
  contexto sintáctico de toda la clase y la admisión de estilo cuenta como
  introducidas sus 30 líneas largas heredadas, entre ellas dos tablas RST de
  su docstring que no se parten sin rehacerlas. Queda para una unidad que
  rehaga ese docstring; la conducta no cambia (los mismos objetos función en
  el mismo dueño).
- RED (`tests/unit/orm/test_relational_multi_class.py`): fallo de colección,
  `_RelationalMulti` no existía. GREEN: 6 passed, más
  `test_compute_onchange.py` y `test_one2many.py` (36 passed en total).
- Control: renombrar `create` en la clase hace caer exactamente
  `test_the_django_owner_carries_the_same_function[create]`.
- Inventario sobre el árbol: ausentes **365 → 360** (`_RelationalMulti`
  clase y cuatro métodos pasan de `absent` a `not_verified`). Pasar a
  `satisfied` exige la columna de evidencia por conducta del censo (diseño
  de arriba), aún no construida.
- Gate completo de la primera forma (con herencia): **12 602 passed, 66
  skipped, 6 xfailed, 0 failed, 5 errors** en 571 s.
- Gate completo de la forma final (instalador en los dos dueños, sin la
  prueba de `issubclass`): **12 601 passed, 66 skipped, 6 xfailed, 0 failed,
  5 errors** en 570 s. La diferencia de uno con la primera forma es esa
  prueba retirada; los 5 errores son los de `test_multidb_isolation.py`
  (fixture que exige una base por defecto desechable).

## Pendiente

- `test_copy_batch` (`test_onchange.py:1013-1024`): necesita
  `test_orm.partner` y `assertQueryCount`.
- `_Relational`/`_RelationalMulti` como clases, sus atributos (`check_company`,
  `context`, `domain`, `relational`), `convert_to_record_multi` de `Many2one`
  y `_Relational`, `update_db_foreign_key(s)`: inventario de `c9c7b545`,
  TASK-API-0485.
- Los dos `xfail(strict=True)` de SQL siguen con TASK-API-0510.
