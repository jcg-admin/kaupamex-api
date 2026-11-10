# `Environment.__getitem__` devuelve un recordset (TASK-API-0485)

Estado: diagnóstico medido sobre `c9c7b545`. El diseño de la transición se
decide aquí y se implementa por grupos coherentes.

## Contrato de la referencia

`odoo19c: odoo/orm/environments.py:105-107` (odoo-tools `abe4040ec1`):

```python
def __getitem__(self, model_name: str) -> BaseModel:
    """ Return an empty recordset from the given model. """
    return self.registry[model_name](self, (), ())
```

`env['x']` es **un recordset vacío** con el entorno, no la clase. La fuente
nunca llama al modelo desde la clase: `self.env['res.currency.rate']` en
`models.py:1976` es el recordset.

## Estado aquí

`src/orm/environments.py:929-952` devuelve la **clase** (`MODELS_BY_NAME`) y,
como respaldo, la etiqueta de Django. La diferencia se cubre hoy con dos
mecanismos:

- el descriptor `_on_empty_recordset` (`src/orm/models.py:6168`), aplicado a
  11 métodos, que entrega `owner._from_ids(env(), (), ())` cuando se llaman
  sobre la clase;
- `env['x'].browse(())` en el código que necesita el recordset (13 llamadas
  `_from_ids(env(), (), ())` en `src` y `addons`).

`src/orm/models.py:7186` escribe `self.env['res.currency.rate']()`
—instancia la clase— donde la fuente lee el recordset (`models.py:1976`).
No es un defecto suelto: `res.currency.rate` no deriva de `BaseModel`
(`src/addons/base/models/res_currency.py:891`), así que no tiene recordset,
y una fila sin guardar es la única forma de llamar a `_field_to_sql`, que
es método de instancia. Se resuelve cuando el modelo adopte `BaseModel`
(TASK-API-0397), no cambiando la línea.

## Consumidores que dependen de la clase (medido)

Instrumento: `probes/env_flow_census.py` (uso directo de `env[...]`, y
`X = env[...]` seguido dentro de su función).

| Uso que exige la clase | Total | Ejemplos |
|---|---|---|
| `X.objects` | 37 (+1 directo) | `src/modules/loading.py:184`, `src/orm/models.py:4737`, `src/orm/fields_relational.py:2294` |
| `X is …` | 15 (+6 directos, todos en tests) | `src/modules/loading.py:137`, `src/orm/models.py:4974` |
| `isinstance(…, X)` | 15 | `src/orm/fields_relational.py:733`, `src/orm/models.py:5898` |
| `issubclass(X, …)` | 8 | `src/orm/models.py:5100`, `:5899`, `:5998` |
| `X(...)` | 6 (+1 directo) | `src/orm/models.py:2244`, `:2611`, `:4301`, `:7186` |
| `X._base_manager` / `_default_manager` | 9 | `src/orm/models.py:1739`, `src/orm/fields_relational.py:714` |
| `type(X)` | 2 | `tests/integration/test_orm/test_env_alias_recordset.py:75` |

Reparto: 50 en `src` + `addons`, 48 en `tests`.

*Métrica:* nodos AST cuyo valor viene de `env[...]` (directo o por una
variable asignada en la misma función) usados en una de esas posiciones.
*Ciega a:* el flujo entre funciones (una clase devuelta y usada en otro
sitio); una variable reasignada con otro origen en la misma función, que
se cuenta igual —el conteo es una cota superior por sitio y una cota
inferior por flujo—; los comodelos de Django (`res.users`, `res.groups`),
que no son `BaseModel` y seguirán devolviendo la clase.

## Lo que el cambio tiene que preservar

1. **Comodelos de Django**: no tienen recordset (`_from_ids`). `env['x']`
   sobre ellos sigue devolviendo la clase. **Divergencia declarada**, con la
   misma razón que en `many2many-write-family.md`: la referencia no tiene
   modelos que no sean `BaseModel`.
2. **El gestor de Django** (`objects`, `_base_manager`): un manager no se
   alcanza desde una instancia (`Manager isn't accessible via … instances`).
   Cada consumidor pasa a `type(records)` o a `records._model_class` (nombre
   a fijar), o se reescribe al método del ORM equivalente.
3. **Identidad e herencia** (`is`, `issubclass`, `isinstance(…, X)`): se
   comparan clases; pasan a `type(env['x'])`.
4. **Llamadas `X(...)`**: instanciar un modelo de Django. Cada una se
   revisa contra la fuente; la de `:7186` es un defecto y se corrige.

## Transición por grupos

| Grupo | Contenido | Prueba |
|---|---|---|
| G0 | `res.currency.rate` adopta `BaseModel`; entonces `:7186` lee el recordset, como la fuente | `test_sum_currency_joins_the_latest_rate` |
| G1 | los 50 consumidores de `src`/`addons` pasan a no depender de que `env[...]` sea la clase (`type(...)`, métodos del ORM) — sin cambiar todavía `__getitem__` | regresión completa: comportamiento igual |
| G2 | `__getitem__` devuelve `model._from_ids(self, (), ())` para un `BaseModel` | `test_environment_mapping.py` y las 6 aserciones `is` de tests pasan a comparar `type(...)`, con su razón |
| G3 | `_on_empty_recordset` y los `browse(())` defensivos quedan redundantes: se retiran | anulación: retirar G2 hace caer las pruebas de G2 |

G1 antes que G2 porque deja el cambio de contrato en un solo commit
pequeño y reversible; G1 es neutro por construcción y su verde no prueba
nada por sí solo, por eso su control es G2.

## G1 — el acceso a la clase tiene su forma en la fuente

Quien necesita la **clase** en la fuente no usa `env[name]`: usa
`self.pool[name]` o `env.registry[name]`. `Registry` es un
`Mapping[str, type[BaseModel]]` (`odoo19c: odoo/orm/registry.py:84`, con
`__len__`, `__iter__` y `__getitem__` en `:309-320`). Aquí `env.registry`
devuelve el **módulo** `orm.registry` (`src/orm/environments.py:1172`), que
no es indexable: medido, `env.registry['test_orm.shared.compute']` da
`TypeError: 'module' object is not subscriptable`.

Sitios que dependen de la clase en `src`/`addons`, por archivo (sondeo
`env_flow_census.py`, sin duplicados): `src/orm/models.py` 34,
`src/orm/fields_relational.py` 10, `src/modules/loading.py` 3.

Decisión: **REUSE**. La búsqueda encontró la autoridad que ya posee la
responsabilidad: `class Registry(Mapping)` (`src/orm/registry.py:1771`), con
`__len__`/`__iter__`/`__getitem__` (`:2981-2991`) y su suite
`tests/unit/orm/test_registry_class.py`. Medido:
`Registry('default')['test_orm.shared.compute']` devuelve la clase, y
`set(Registry('default')) == set(MODELS_BY_NAME)` (205 nombres). Lo que
falta es que `env.registry` devuelva **esa instancia** (≙ `env.registry`,
`odoo19c: odoo/orm/environments.py:172`) y no el módulo.

Consumidores actuales de `env.registry.<x>` que hay que mantener: `clear_cache`
(7) y `field_triggers` sólo existen en el módulo; `db_name`, `unaccent`,
`_init_modules`, `ready`, `has_trigram`, `_setup_models__` sólo en la
instancia (hoy darían `AttributeError` por `env.registry`, que devuelve el
módulo); `field_depends`, `field_depends_context`, `field_inverses`,
`field_computed`, `not_null_fields`, `models` en los dos. El cambio de
`Environment.registry` exige antes que `clear_cache` y `field_triggers`
respondan en la instancia (≙ `Registry.clear_cache` y
`Registry.field_triggers` de la fuente), delegando en las funciones del
módulo, que siguen siendo el eje de proceso.

Después, cada uno de los 47 sitios pasa de `env[name]` a
`env.registry[name]` o a `type(records)`, como la fuente, y el
comportamiento no cambia mientras `env[name]` siga siendo la clase. G2 cambia
`__getitem__` sobre un árbol que ya no depende de ella.

**Refinamiento de los 47 sitios.** El sondeo cuenta una variable asignada
desde `env[...]` en cualquier punto de la función, así que incluye variables
como `comodel` que en el sitio contado vienen de `field.related_model`. Y G2
sólo cambia el resultado para un `BaseModel`: un modelo de Django sigue
devolviendo la clase. Leídos los seis primeros de `models.py`
(`:1739`, `:2076`, `:2244`, `:2611`, `:4308`, `:7238`), cinco ya distinguen
los dos casos (`hasattr(comodel, '_from_ids')`, `issubclass(comodel,
DefaultGetMixin)`, `hasattr(model, '_has_field_access')`) o son de un
comodelo de Django (`res.currency.rate`). La clasificación definitiva se
hace sitio por sitio en la implementación de G1, con tres desenlaces:
*afectado por G2* (cambia a `env.registry[name]` o `type(records)`),
*ya bifurca* (sin cambio) y *sólo Django* (sin cambio, cubierto por la
divergencia declarada).

Pruebas de G1: `env.registry[name] is` la clase registrada; `in`, `len` e
iteración sobre los nombres; `KeyError` ante un nombre desconocido (≙
`:317-320`).

## G1a — implementación

- `Registry.clear_cache(*cache_names)` en la instancia (≙ `registry.py:971-987`),
  delegando en `orm.registry.clear_cache`, el eje de proceso.
- `Environment.registry` devuelve `registry.Registry(self.db_alias)`, la misma
  base que `env.cr`.
- Textos corregidos donde decían que `env.registry` era el módulo
  (`src/orm/registry.py`, `src/orm/models.py` en `_read_group_expand_full` y
  en `_is_an_ordinary_table`, que pasa a leer `self.env.registry` como
  `self.pool` de la fuente).

Pruebas (`tests/unit/orm/test_environment_registry.py`): RED 4 failed sobre
`c5c5ff29` (la de `clear_cache` pasaba sin discriminar mientras
`env.registry` era el módulo; se le añadió `'clear_cache' in vars(Registry)`),
GREEN 4 passed. Consumidores de `env.registry.<x>`: `base_automation`, `crm`,
`ir_rule`, `ir_ui_menu`, `res_currency`, `res_users`, `fields.py`
(`unaccent`), `models.py`; su subconjunto derivado abarca 49 directorios de
`tests/`, así que la verificación es el gate completo.

**Primer gate completo de G1a: 7 failed.** `Environment.cache_key` leía
`self.registry.field_depends_context`; con `env.registry` como instancia, ese
mapa era una **copia** tomada en `Registry.init` (`self.field_depends_context
= field_depends_context`), y las pruebas que parchean el global del módulo
(`test_environments_cache.py`, `test_uid_cache_key_contract.py`) leían otro
objeto. Ningún código de producción reasigna esos globales, pero la copia
contradecía el propio comentario de `init` («ejes derivados, compartidos con
el proceso»). Corrección: `field_depends`, `field_depends_context` y
`many2one_company_dependents` pasan a ser propiedades de `Registry` que leen
el global del módulo, su único dueño.

Controles de anulación sobre `test_environments_cache.py`,
`test_uid_cache_key_contract.py`, `test_environment_registry.py` y
`test_registry_class.py` (93 casos):

| Anulación | Caen |
|---|---|
| `env.registry` devuelve el módulo | 3 (las de mapa, identidad y `KeyError`; la de `clear_cache` mide `Registry.clear_cache`, que esta anulación no retira) |
| `field_depends_context` copiado en `init` | 7 (las de `cache_key`) |

Segundo gate completo (árbol principal sobre `1d75518a` más G1a): **12 593
passed, 66 skipped, 6 xfailed, 0 failed, 5 errors** en 692 s; los 5 errores
son los de `test_multidb_isolation.py` (base desechable de `ci-multidb`).

Después del gate, la admisión de estilo pidió dos cambios sin efecto en la
conducta: los cuatro miembros nuevos de `Registry` (`field_depends`,
`field_depends_context`, `many2one_company_dependents`, `clear_cache`) se
mueven al final de la clase —la huella de la admisión incluye la posición de
cada sentencia en su contenedor, e insertarlos a mitad desplazaba la de los
miembros siguientes— y el docstring del módulo se reescribe en 79 columnas
(su tabla describía todavía un puerto sin `Registry`). Las 93 pruebas de las
cuatro suites afectadas siguen en verde tras el cambio.

## Pendiente

- Medir el flujo entre funciones (clases devueltas por funciones auxiliares
  como `_inherits_parent`).
- Fijar el accesor de la clase desde un recordset (`type(records)` es lo que
  usa la fuente; preferirlo sobre un nombre nuevo).
