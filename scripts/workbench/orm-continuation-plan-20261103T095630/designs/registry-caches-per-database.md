# Cachés e invalidación por base: el `Registry` de la fuente es por base

Creado: 2026-11-12T10:53:42 (UTC). TASK-API-0485. Origen: §4 de la
instrucción operativa del ejecutor (verificar la corrección de
`IrModelData._update_xmlids`, `registry.Registry(using).cache_invalidated`).

## Lo que corrigió el lote 4, y lo que no

La carga de datos de `uom` activó la rama de reasignación de xml-id de
`_update_xmlids` (`src/addons/base/models/ir_model.py`), que llamaba a un
atributo inexistente del módulo `orm.registry`. Se cambió a
`registry.Registry(using).cache_invalidated.add('default')`, el
`self.env.registry.cache_invalidated.add('default')` de
`odoo19c: odoo/addons/base/models/ir_model.py:2402`. Esa corrección elimina
el `AttributeError` y anota la invalidación. **No** reproduce la propiedad
de la fuente, porque el conjunto que devuelve no es de esa base.

## El contrato de la fuente

| Pieza | Fuente | Este árbol |
|---|---|---|
| contenedores de caché | `self.__caches` **por instancia** de `Registry`, una por base (`odoo/orm/registry.py:233`) | `_CACHES`, del **módulo**: uno por proceso (`src/orm/registry.py:173`) |
| registro de invalidación | `self._invalidation_flags = threading.local()` **por instancia** (`:282`), leído en `cache_invalidated` (`:1028-1034`) | `_invalidation`, `threading.local` del **módulo**, devuelto por `cache_invalidated_names()` a todo `Registry` |
| `clear_cache` | vacía los contenedores **de ese registro** y anota en él (`:970-995`) | vacía el contenedor del proceso y anota en el registro del hilo |
| `signal_changes` | inserta en las tablas de señalización **de su base** lo que ESE registro invalidó (`:1118-1141`) | inserta en su base lo que **cualquier** registro del hilo invalidó |

Las entradas de `ormcache` llevan el alias en la clave (por ejemplo
`_xmlid_lookup.__cache__.add_value(cls, key, using, ...)`), así que no hay
**lectura cruzada**. Lo que hay es **invalidación cruzada**: una reasignación
de xml-id en la base A vacía también las entradas de B y, si el registro de B
señala después en el mismo hilo, anuncia a los demás procesos de B un cambio
que B nunca tuvo. Es exceso de invalidación, no un valor incorrecto, pero
diverge del contrato.

## Corrección propuesta (unidad siguiente, no del candidato en verificación)

1. `Registry.__init__` crea `self._invalidation_flags = threading.local()` y
   `cache_invalidated` lo lee, como la fuente.
2. Los contenedores pasan a ser por base: `_CACHES` se indexa por el alias
   del registro y `cache_of(cache)` resuelve con el registro de la entrada;
   `clear_cache(*names)` del módulo delega en el registro del entorno activo.
3. Las pruebas de §4 se escriben antes:
   - actualización de un xml-id existente (`created != written`): el modelo,
     el `res_id` y el registro de la fila coinciden;
   - la invalidación es efectiva en la base que reasignó;
   - **no** hay invalidación ni señalización en la otra base (dos registros,
     dos alias): RED hoy;
   - `IrModelData.ref` resuelve tras la reasignación; repetir la carga no
     escribe (idempotencia: `RETURNING` sin cambios);
   - un rollback de la reasignación no deja el xml-id movido ni la caché
     sembrada con el destino deshecho.

## Estado de DecimalPrecision (§5)

`tests/unit/base/test_decimal_precision.py` cambió los nombres `Product
Price`/`Product Unit` por `Probe Price`/`Probe Unit` en
`test_it_takes_a_list_and_returns_the_records`, porque `uom_data.xml`
siembra `Product Unit`. Sus dos aserciones se conservan (los nombres
devueltos en orden y el conteo por nombre); el diff de `e5ef3952` sobre ese
archivo es de 7 líneas añadidas y 5 retiradas, todas en esa prueba y su
comentario. La unicidad de `decimal.precision.name` la sigue verificando el
mismo archivo (`decimal_precision_name_uniq` y el `IntegrityError` de las
líneas 146-150). Los datos de referencia (`addons/uom/data/uom_data.xml`) no
se tocaron.

## Corrección medida 2026-11-12T13:37:56 (UTC): sí hay lectura cruzada

El párrafo «Las entradas de `ormcache` llevan el alias en la clave … no hay
lectura cruzada» es **falso** para la mayoría de los métodos. Censo por AST de
los decoradores `ormcache`/`ormcache_context` de `src/` y `addons/`
(`outputs/ormcache-key-census.tsv`): **15** métodos, **4** con el alias en la
clave (`_get_param`, `_get_model_defaults`, `_xmlid_lookup`,
`_get_definition_id_for_property_field`) y **11** sin él. La clave que arma
`ormcache.determine_key` es `(receptor._name, method, *args)`, igual que la
fuente; la fuente no necesita el alias porque el **contenedor** es del
registro de la base (`model.pool._Registry__caches`,
`odoo19c: odoo/tools/cache.py:101,127`). Aquí el contenedor es del proceso,
así que dos bases comparten la entrada:

| Método sin alias | Qué devolvería a la otra base |
|---|---|
| `IrModel._get_id`, `_get_ids` | ids de `ir.model` de la primera base que los pidió |
| `IrRule._compute_domain` | el dominio de reglas de registro calculado con los grupos de la otra base: **es de seguridad** |
| `IrModelAccess._get_access_groups`, `_allowed_models_for_groups` | los grupos con acceso de la otra base |
| `DecimalPrecision.precision_get` | la precisión configurada en la otra base |
| `ResLang._get_active_by`, `ResGroups._get_group_definitions`/`_get_view_group_hierarchy`, `IrDefault._get_field_column_fallbacks`, `ResCompany._get_zeep_cache__` | datos de la otra base |

*Métrica:* decoradores `ormcache` por AST y si alguno de sus argumentos de
clave nombra `using`/`alias`/`db`. *Ciega a:* una clave que lleve la base
por otro nombre (p. ej. un id de compañía que en la práctica identifica la
base) y a cachés manuales fuera del decorador.

Por eso la unidad no se resuelve añadiendo `using` a 11 claves —eso sería
apartarse de la fuente método por método— sino con el contenedor por registro,
que es la forma de la fuente:

1. `Registry.__init__` crea `self._caches = {nombre: LRU(tamaño)}` y
   `self._invalidation_flags`; `cache_invalidated` lee
   `self._invalidation_flags.cache` (`registry.py:233,282,1026-1033`).
2. `Registry.clear_cache`/`clear_all_caches` vacían **sus** contenedores y
   anotan en **su** registro de invalidación (`:970-1001`); `load`,
   `_setup_models__`, `check_signaling` y `reset_changes` usan
   `self._caches`.
3. `ormcache.lookup`/`add_value` resuelven el registro del receptor:
   `receptor.env.registry` si es un recordset, si no el del entorno activo
   (`orm.environments.env().registry`) — los receptores `classmethod` no
   llevan entorno propio.
4. Las funciones de módulo `cache_of`/`clear_cache`/`clear_all_caches`
   delegan en el registro del entorno activo; `cache_invalidated_names` y
   `reset_invalidation_record` se retiran y sus 7 consumidores leen la
   instancia.

## Pruebas, escritas antes (RED)

- lectura: una entrada sembrada bajo el registro de `default` **no** se
  sirve bajo el registro de otro alias (el segundo `lookup` es un fallo de
  caché y ejecuta el método);
- invalidación: `clear_cache('default')` bajo un alias no vacía el
  contenedor ni anota en el registro del otro;
- señalización: `signal_changes` de un registro sólo inserta lo que **ese**
  registro invalidó;
- §4 de la instrucción: reasignación de xml-id (`created != written`),
  `ref` tras reasignar, idempotencia de la recarga y rollback de la
  reasignación sin caché sembrada con el destino deshecho.

## Precondición medida 2026-11-12T13:41:51 (UTC): el registro se pide por la base, no por el cursor

`Environment.registry` devuelve `registry.Registry(self.db_alias)`
(`src/orm/environments.py:1188-1199`), y desde `663aac8b` el alias de un
`sql_db.Cursor` es efímero: `<alias>__cursor_<n>` (`src/sql_db.py:200`).
Un entorno sobre el cursor de una unidad de trabajo —el de cada trabajo del
cron, el de `Registry.new`— pide entonces `Registry('default__cursor_7')`,
que no está en `Registry.registries` y se **construye** con
`Registry.new`: un registro por cursor, en un LRU de 42 entradas que puede
desalojar al de la base. En la fuente la clave es `cr.dbname`
(`odoo19c: odoo/orm/environments.py:72`: la transacción nace con
`Transaction(Registry(cr.dbname))` y el entorno lee `transaction.registry`),
que es la base y no la conexión.

Con cachés por registro esto deja de ser sólo coste: un `clear_cache` hecho
dentro de un trabajo del cron caería en el registro del cursor y el de la base
seguiría sirviendo lo invalidado. Por eso la unidad lo corrige primero:

- `sql_db` recuerda el alias de origen de cada cursor efímero y
  `origin_alias(alias)` lo devuelve (el propio alias si no es efímero);
- `registry.registry_for_alias(alias)` resuelve el registro por el origen;
  `Environment.registry` y `registry_of` lo usan.

RED: un entorno sobre el cursor real de `Registry('default').cursor()` tiene
`env.registry is Registry('default')`.

## Frontera abierta: nadie señaliza ni deshace

En este árbol ningún llamador ejecuta `Registry.signal_changes()` ni
`reset_changes()` (sólo el `manage_changes` deprecado). En la fuente los
llaman el ciclo de `retrying`/`execute_cr`
(`odoo/service/model.py:134-136,197,235-240`), el despacho HTTP y `load`
(`odoo/orm/models.py:1061-1063`, *"cancel all changes done to the
registry/ormcache"*). Sin ellos la invalidación anotada no llega a los demás
procesos y un rollback no la deshace. Esta unidad porta el de `load`, que vive
en el ORM; el del ciclo de petición (middleware de Django, comando de
gestión, cron) es una unidad propia: `registry-signaling-lifecycle-0485`.

## Implementación y verificación (2026-11-12T14:04:26 UTC)

| Pieza | Dónde |
|---|---|
| contenedores y `cache_invalidated` por instancia; `clear_cache`/`clear_all_caches` del registro | `src/orm/registry.py` (`Registry.init`, `cache_invalidated`, `clear_cache`, `clear_all_caches`, `load`, `_setup_models__`, `check_signaling`, `reset_changes`) |
| registro por base, no por cursor | `sql_db.origin_alias`, `registry.registry_for_alias`, `Environment.registry` |
| funciones de módulo sobre el registro activo | `registry.active_registry`, `cache_of`, `clear_cache`, `clear_all_caches`, `cache_invalidated_names` |
| `ormcache` con el contenedor y el contador `(base, método)` del registro | `src/tools/cache.py` (`ormcache.registry_of`: el `using` declarado o el receptor) |
| claves de la fuente sin `using` | `_get_param`, `_get_model_defaults`, `_xmlid_lookup`, `_get_definition_id_for_property_field` |
| `_update_xmlids` anota e invalida `groups` en el registro de `using` | `ir_model.py` |
| `load` deshace lo anotado al revertir | `orm/models.py` (≙ `models.py:1061-1063`) |

RED (`outputs/registry-caches/red-caches.log`, `red-xmlid-and-cursor.log`):
5 de 8; la lectura cruzada devolvió bajo el alias de sondeo el id cacheado
desde `default` (`66301`) con la fila de esa base renombrada. GREEN: 44
passed con el contrato de `tools/cache.py` y `test_ormcache`. Anulación
(`nullify-caches.log`): contenedor único → cae 1; sin `origin_alias` → caen
2; `load` sin `reset_changes` → cae 1; registro de invalidación compartido →
caen 2. Los archivos se restauraron byte a byte.

Las tres pruebas que pasan antes y después (reasignación anotada,
idempotencia, `reset_changes` tras deshacer) no son RED: con el registro de
invalidación del módulo ya pasaban. Quedan como guardas.

*Ciega a:* dos bases físicas distintas — las pruebas usan dos alias sobre la
misma base, cada uno en su transacción; eso lo cubre ci-multidb.
