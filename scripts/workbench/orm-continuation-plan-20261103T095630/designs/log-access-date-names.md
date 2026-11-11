# Los nombres contractuales de las fechas: create_date y write_date

Fecha: 2026-11-11 · TASK-API-0485, hija B de `designs/log-access-columns-audit.md`.
Directiva del ejecutor del 2026-11-11 (§5): la referencia fija los nombres
`create_date`/`write_date`. La decisión no se deja al ejecutor: se
implementan distinguiendo tres superficies.

## Las tres superficies

| Superficie | Hoy | Después | Mecanismo |
|---|---|---|---|
| 1. Nombre del campo ORM | `created_at` / `updated_at` | **`create_date` / `write_date`**, como `odoo19c: odoo/orm/models.py:287-292,296` | renombre del campo en `TimeStampedModel` y `TransientModel` |
| 2. Columna PostgreSQL | `created_at` / `updated_at` | **sin cambio** | `db_column='created_at'` / `'updated_at'` en el campo |
| 3. Nombre externo de la API v2 | `created_at` / `updated_at` | **sin cambio** mientras el contrato vigente lo exija | `serializers.DateTimeField(source='create_date', read_only=True)` en cada serializador que lo expone |

**TRAE:** Django separa nombre de campo y columna (`Field.db_column`), y la
migración de estado (`migrations.SeparateDatabaseAndState`) cambia el estado
del autodetector sin emitir SQL. DRF separa el nombre externo del atributo
(`Field.source`).

Así hay **una sola columna y un solo valor**: no hay campo duplicado ni
sincronización entre dos fuentes. Un renombre físico de columna se descarta.
Costaría un `ALTER TABLE … RENAME` en 352 tablas de cada base de compañía y
no aporta nada al contrato, que se fija en el nombre ORM.

## Matriz de consumidores (medida el 2026-11-11, sin migraciones)

| Uso | Apariciones | Archivos | Tratamiento |
|---|---|---|---|
| atributo `.created_at` / `.updated_at` | 57 | 30 | → `.create_date` / `.write_date` |
| cadena de lookup u orden (`'-created_at'`, `'created_at__gte'`) | 389 | 165 | → nombre contractual, salvo claves de una API externa (por cada aparición) |
| kwarg (`created_at=`, `updated_at__lt=`) | 92 | 50 | → nombre contractual |
| serializadores que lo nombran | — | 16 | `Meta.fields` conserva el nombre externo; se declara el campo con `source=` |
| claves de una respuesta construida a mano (`'created_at': …`) | 9 | 6 | la clave externa no cambia; el valor lee el nombre contractual |

Casos especiales:

- `TransientModel` (`src/orm/models_transient.py:84-85`) declara sus
  propias fechas → mismo renombre con `db_column`. `_transient_clean_rows_older_than`
  y `models_transient.py:159-173` leen `'updated_at'` → `write_date`.
- `LOG_ACCESS_COLUMNS` pasa a `['create_uid', 'create_date', 'write_uid',
  'write_date']`, idéntica a la fuente. `write()` y el volcado de filas
  nombran `write_date`.
- Modelos que redeclaran la fecha con otro contrato: `sale.order`
  (`addons/sale/models/sale_order.py:256`, `db_index=True`),
  `checkout_attempt` y `rating/review`. Se revisan uno por uno contra la
  fuente: `sale.order` en Odoo no declara `create_date`; su índice se mueve
  a `Meta.indexes` sobre `create_date`.
- `hr.employee.public` ya declara `create_date`: es el nombre contractual y
  no cambia.
- `src/tools/profiler.py:718-724` escribe `"created_at"` en un diccionario.
  Se revisa si es una fila de la base o un registro propio.

## Migración

Una migración de estado por app, que se genera con un script y no con
`makemigrations`, porque el autodetector preguntaría interactivamente si es
un renombre. Para cada modelo con la fecha heredada:

```python
migrations.SeparateDatabaseAndState(state_operations=[
    migrations.RenameField(model, 'created_at', 'create_date'),
    migrations.AlterField(model, 'create_date',
                          models.DateTimeField(auto_now_add=True,
                                               db_column='created_at')),
    … ídem write_date …
], database_operations=[])
```

Verificación: `makemigrations --check` vacío, y
`sqlmigrate` de la migración sin ninguna sentencia.

## Pruebas

- El campo `create_date` existe, su columna es `created_at`, y
  `Model.objects.filter(create_date__lte=…)` traduce a la columna física
  (afirmación sobre el SQL).
- `LOG_ACCESS_COLUMNS` es igual a la de la fuente.
- La API v2 conserva su contrato: un serializador representativo sigue
  emitiendo `created_at` con el valor de `create_date`.
- Antes, durante y después: una fila creada antes de la migración conserva su
  fecha (la columna no cambia), y una escritura posterior mueve `write_date`.
- Gate completo y ci-multidb.

## Orden

Después de la hija A (columnas de usuario, en gate) y de la hija C
(autoinyección), porque C copia los campos de `TimeStampedModel`. Si B fuera
antes, C los copiaría con el nombre nuevo, lo cual también es válido. Se
elige A → C → B para que cada gate mida un cambio, no tres.

## Revisión del mecanismo (2026-11-11, antes de implementar)

La primera versión mantenía la columna física con `db_column`. Al medir los
consumidores apareció el problema: el SQL crudo nombra la **columna**
(`src/addons/base/models/ir_model.py:3354-3355`, `src/tools/profiler.py:718-724`,
`tests/unit/orm/test_read_group_groupby.py:90`), y el ORM nombraría el
**campo**. Dos nombres para una misma fecha según la capa obligan a decidir
cada aparición de `'created_at'` por su contexto, y un renombre por texto no
puede hacerlo.

**Mecanismo adoptado: renombre también físico.** `migrations.RenameField`
emite `ALTER TABLE … RENAME COLUMN`. En PostgreSQL es un cambio de catálogo:
no reescribe filas, es transaccional y es instantáneo con independencia del
tamaño de la tabla. Con él:

- superficie 1 (ORM) y 2 (columna) usan el mismo nombre, el de la fuente;
- superficie 3 (API v2) conserva `created_at`/`updated_at` con `source=`;
- el árbol tiene **un** nombre interno, así que el renombre es uniforme, y
  las excepciones son solo las de la API externa y se enumeran.

Excepciones medidas, que **conservan** el nombre antiguo:

| Sitio | Por qué |
|---|---|
| `Meta.fields`/`read_only_fields` de los 16 serializadores | nombre externo de la API v2: se declara `created_at = DateTimeField(source='create_date', read_only=True)` |
| claves de respuestas construidas a mano (`addons/mass_mailing/services.py:74`, `src/addons/base/controllers/admin_main.py:174`) | nombre externo; el valor pasa a leer `create_date` |
| subíndices de respuestas de API en pruebas (`response.data['created_at']`) | aserción sobre el contrato externo |

El resto, incluido el SQL crudo, pasa al nombre contractual.
`CheckoutAttempt` (propio, sin `TimeStampedModel`) declara su propio
`created_at`. Se renombra igual: es la fecha de creación de la fila, y dejar
un tercer nombre volvería a abrir la ambigüedad.

Antes, durante y después: la migración de renombre se prueba sobre una fila
creada antes de aplicarla, y su fecha tiene que sobrevivir.


## Extensión medida (2026-11-11): las columnas de autoría también toman el nombre de la fuente

El gate completo de la unidad C (`04cd6f80`) falló en `check_fk_naming`.
Los dos FK de autoría de `hr.employee.public` salían en forma D. La fuente no
los declara en el archivo del modelo, sino en el metaclase (`odoo19c:
odoo/orm/models.py:287-292`), y el gate sólo consultaba la contraparte del
archivo. Se corrigió en dos sitios:

- el gate conoce `create_uid`/`write_uid` como símbolos de la fuente para
  todo modelo (`SOURCE_METACLASS_MANY2ONE`);
- `hr.employee.public` los declara en forma C (`db_column='create_uid'`), y
  su vista los selecciona con ese alias.

**Lo que queda, y es de esta unidad:** las columnas `create_uid_id` y
`write_uid_id` que creó la unidad A en las tablas. En la fuente la columna se
llama `create_uid`. `LogAccessUserField` no es un constructor que
`check_fk_naming` reconozca (`SINGLE_VALUED`), así que hoy el gate no las ve.
Su renombre físico (`db_column` y `RENAME COLUMN`, el mismo mecanismo de las
fechas) se añade a B para que las tres superficies coincidan con la fuente en
las cuatro columnas. El gate también tiene que reconocer el constructor.

## Verificación (2026-11-11, sobre `7eb9508a`)

- **Migraciones.** 74 `*_log_access_date_names` con 754 `RenameField`, 96
  `AlterModelOptions` y 8 pares de índices. Otras 74
  `*_log_access_user_column_names` con 752 `AlterField` (`db_column`), que
  cubren 376 modelos × 2 columnas de autoría. `makemigrations --check`: sin
  cambios. `check --database default`: sin errores. Las dos de `product` se
  renumeraron a 0020/0021 detrás de `0019_favorite_index_short_name`.
- **Base nueva** (`orm_x2hokp_wtb`, `--create-db`): 62 de 62 en las pruebas de
  A, B, C, la operación de cómputo, el lookup de xmlid y el gate de FK.
- **Antes y después** (`outputs/gates/preservation-logaccess-b`). Una base
  sembrada en el estado C y migrada a B conserva `id`, las dos fechas y los
  dos usuarios en las 1084 filas de la muestra, con conteos iguales. La única
  columna con nombre viejo es `token_blacklist_outstandingtoken.created_at`,
  de `rest_framework_simplejwt`, fuera del log-access (DEC-09).
- **Coste del renombre de autoría.** Cambiar `db_column` en un `ForeignKey`
  hace que Django borre y recree la restricción FK, y recrearla valida la
  tabla. Es lineal en filas, a diferencia del `RENAME COLUMN` de las fechas,
  que es de catálogo.
- **Anulaciones** (base: 29 de 29 en `test_log_access_date_names` +
  `test_check_fk_naming`):

  | Mitad anulada | Cae | Sobreviven |
  |---|---|---|
  | `source='create_date'` del serializador de la API v2 | `test_the_api_keeps_its_external_names` | 28 |
  | `LogAccessUserField` en `SINGLE_VALUED` del gate | `test_the_log_access_constructor_is_measured` | 28 |
  | `db_column='create_uid'` en `TimeStampedModel` | las 29, en el montaje | 0 |

  El tercero actúa al cargar las clases: la comprobación de sincronía entre
  modelos y migraciones rechaza el modelo que diverge. Discrimina por sesión,
  no por prueba, igual que las mitades de la unidad C.
- **Estilo.** El renombre toca funciones y clases, y la admisión
  identifica cada hallazgo por el nodo que lo contiene, así que las líneas
  largas previas de esos nodos cuentan como introducidas. Se corrigieron con
  un fijador que sólo acepta un cambio si el AST sin posiciones queda igual
  (salvo el texto de seis docstrings). La constante XML del reporte de venta
  se partió en literales contiguos, y el mismo AST prueba que su valor no
  cambia. Se retiró un `# noqa: D401` inerte: ningún linter del repositorio
  aplica D401.
- **El barrido de residuos tenía un punto ciego, y se midió.** La búsqueda
  del nombre viejo usaba `rg -w`, y `\b` no separa `created_at` de
  `created_at__gte`, porque `_` es carácter de palabra. Quedaron 19 archivos
  con búsquedas por sufijo (`created_at__lt`, `updated_at__gte`, …) y
  `test_bus` falló con `FieldError`. Se repitió el barrido sin `-w`. La única
  población con `created_at` propio es `OutstandingToken` de simplejwt, que
  ningún módulo del árbol consulta, así que se renombraron todos.
- **Identificadores.** `texto`, una clave de datos de prueba, pasa a `text`.
  `doy` (*day of year*) es la clave verbatim de la fuente (`odoo19c:
  odoo/addons/base/models/ir_sequence.py:219`): el léxico la lee como español,
  pero no se puede traducir sin romper el contrato, así que entra al baseline
  como deuda heredada.
