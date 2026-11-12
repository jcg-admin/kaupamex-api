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
