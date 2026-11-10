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

## G2 — medición exploratoria (2026-11-10)

`Environment.__getitem__` devolviendo `model._from_ids(self, (), ())` para un
modelo con recordset (los modelos de Django siguen devolviendo la clase),
sobre `tests/unit/orm`, `tests/integration/test_orm`, `tests/unit/hr_skills`,
`tests/unit/hr_recruitment_skills`, `tests/unit/base` y
`tests/integration/base`: **8 failed, 5854 passed**. Clasificación, sitio por
sitio:

| Prueba | Causa | Forma de la fuente |
|---|---|---|
| `test_parent_store.py` (2), `test_compute_onchange.py::…queryset` | `env[name].objects`: el gestor de Django no se alcanza desde una instancia | `type(env[name]).objects` (el gestor es de la clase) |
| `test_timestamped_transaction_now.py::…clock_again` | `env[name]()` instancia la clase | `type(env[name])()` |
| `test_environment_mapping.py::test_get_returns_the_model_or_the_default` | `env.get(name) is clase` | la fuente devuelve un recordset: se compara `type(...)` |
| `test_fields_registry_declared_one2many.py` | `vars(Discussion)` sobre un recordset lee el `__dict__` de la instancia | `vars(type(Discussion))` |
| `test_domain.py::test_optimize_level_by_level` | `monkeypatch.setattr(env[name], …)` parchea la instancia | parchear `type(env[name])` |
| `test_search.py::test_the_context_lifts_the_filter` | `context_scope(active_test=False)` es el contexto ambiente; el recordset obedece al contexto de **su** entorno | `env[name].with_context(active_test=False)` (≙ la prueba de la fuente) |

Ninguno es un defecto del contrato: son pruebas que asumían la clase o el
contexto ambiente. Comprobado aparte que `recordset._fields` y `clase._fields`
contienen lo mismo (`set(cls._fields) - set(rec._fields)` vacío). G2 se
implementa con esas ocho adaptaciones y se verifica con el gate completo,
porque los addons no entraron en esta medición.

## G2 — implementación

`Environment.__getitem__` devuelve `model._from_ids(self, (), ())` para un
modelo con recordset; un modelo de Django sin `BaseModel` sigue devolviendo
su clase. Las ocho pruebas de la medición se llevan a la forma de la fuente
(tabla de arriba).

Pruebas nuevas, `tests/unit/orm/test_environment_getitem.py`: `env[name]`
es un recordset vacío del modelo con ese entorno; sobre él encadenan
`create`, `browse`, `search`, `new`, `with_context`, `sudo` y `with_user`
sin salir del entorno; un modelo de Django sigue devolviendo su clase. (En la
fuente `uid == SUPERUSER_ID` eleva `su`, `environments.py:66-67`: la prueba
mide `sudo()` y no `sudo(False)`.)

Control de anulación (`if False and hasattr(model, '_from_ids')`): caen
exactamente 4 — las dos de recordset de la suite nueva,
`test_get_returns_the_model_or_the_default` y
`test_the_context_lifts_the_filter` —; sobrevive la del modelo de Django,
que no depende de G2.

Gate completo (árbol principal, base `3b610d63` más G2): **12 596 passed,
66 skipped, 6 xfailed, 0 failed, 5 errors** en 775 s; los 5 errores son los
de `test_multidb_isolation.py`.

Queda **G3**: con `env[name]` como recordset, el descriptor
`_on_empty_recordset` (9 métodos) y los `browse(())` defensivos del árbol
son redundantes; se retiran en su propia unidad, con su control.

## G3 — retirar `_on_empty_recordset` y los `browse(())` defensivos

Diseño escrito antes de tocar código (2026-11-10).

**Qué cubre el descriptor hoy.** `_on_empty_recordset`
(`src/orm/models.py:6220`) envuelve **9** métodos de `BaseModel` (medido con `grep -n
_on_empty_recordset src/orm/models.py`: dos asignaciones y siete
decoradores; la cifra «11» de G2 estaba mal): `flush_model`,
`invalidate_model`, `_write`, `browse`, `new`, `check_access_rights`,
`_is_an_ordinary_table`, `check_field_access_rights` y
`_determine_fields_to_fetch`. Llamado sobre la **clase**, inyecta el recordset vacío del entorno
activo. La fuente no tiene equivalente: sus métodos sólo se llaman sobre
recordsets, porque `env[name]` siempre devuelve uno
(`odoo19c: odoo/orm/environments.py:105`).

**Los `browse(())` del árbol se reparten en dos clases**, y sólo una es
redundante:

| Clase | Sitios | Veredicto |
|---|---|---|
| sobre `env[name]`, que tras G2 ya es el recordset vacío | `fields_relational.py:2345,2467,2561,2700`; `hr_individual_skill_mixin.py:473,519,614,663`; `hr_job.py:112`; `hr_employee.py:264,274` | se retira el `.browse(())` |
| sobre una **clase** (`join` devuelve `related_model`, `cls` de un `classmethod`, el modelo que recibe el exportador) | `fields_relational.py:2364`; `models.py:4148`; `web/controllers/export.py:1163` | se reemplaza por `model.env[cls._name]`/`env[cls._name]`, que es la forma de la fuente; donde no haya entorno a mano se declara |

**El riesgo** está en los llamadores que invocan uno de los 9 métodos sobre
la clase y que un grep no ve (la clase llega por `type(records)`,
`MODELS_BY_NAME`, `related_model` o una función auxiliar). El instrumento es
de conducta: se retira el descriptor y se ejecuta la suite completa; cada
`TypeError`/`AttributeError` por falta de `self` nombra un llamador, que se
corrige pasando por `env[cls._name]`. No se reintroduce un sustituto con
otro nombre.

**Control:** con el descriptor retirado y los llamadores corregidos, una
prueba nueva afirma que `BaseModel.browse` en la clase ya no es un
descriptor (`vars(BaseModel)['browse']` es una función) y que
`env['x'].browse(ids)` sigue funcionando. Reponer el descriptor hace caer la
primera; quitar G2 hace caer la segunda.

## G3 — implementación

Medición exploratoria (descriptor retirado, subconjunto `orm`, `test_orm`,
`base`, `hr*`, `web`): 115 failed y 139 errors. Agrupados por el marco que
llama sobre la clase, los llamadores eran:

| Sitio | Corrección |
|---|---|
| `registry._call_hooks` | `model._from_ids(env(), (), ())._register_hook()`, el `env[name]` de la fuente (`odoo/modules/loading.py:588-595`) |
| `Environment.flush_all` | `model._from_ids(self, (), ()).flush_model()`; el `QuerySet` vacío queda para los modelos de Django |
| `models._flush` | `self.browse(ids)`; la clase o un `QuerySet` del eje de esquema toman el recordset del entorno activo |
| `models._model_of_records` | un recordset lleva su modelo aunque esté vacío; sin esto `flush_all` no volcaba nada (6 fallos del gate) |
| `commands` (One2many y Many2many) | `comodel_records(scope, comodel)`: `env[comodel_name]`; un comodelo de Django sigue como clase con su manager |
| `fields_relational` (`join`, `convert_to_cache` de Many2one y x2many, `write_new_one2many`) | el comodelo es `env[comodel_name]`; `join` devuelve el recordset, como la fuente, y desaparece el `browse(())` posterior |
| `convert._tag_delete` | `env[model._name].browse(pks).unlink()` |
| `models.search_read`, `_search_display_name` | `cls._from_ids(env(), (), ())`, la forma de los métodos de clase envueltos |
| `web/controllers/export.py` | `env[model._name].with_context(...)` |
| `test_orm.bar._search_foo` | vuelve a ser método de instancia, como en la fuente (`self.env['test_orm.foo'].browse(value)`) |

Se retiran los 10 `.browse(())` sobre `env[...]` (`fields_relational` y
`hr_skills`) y `BaseModel.__ror__`, que la fuente no declara y existía por la
misma adaptación. Diez pruebas y rejillas pasan a `env[MODEL]`; las tres
rejillas diferenciales reciben ahora el mismo objeto que la referencia.

Prueba nueva: `tests/unit/orm/test_environment_recordset_only.py` (12 casos).

Controles de anulación:

- reponer el descriptor sobre los 9 métodos y `__ror__`: caen exactamente
  11 de 12 casos de la prueba nueva; sobrevive
  `test_browse_on_the_empty_recordset_keeps_its_environment`, que mide G2;
- retirar la rama `BaseModel` de `_model_of_records`: caen exactamente los 6
  casos de conducta que el gate había marcado (`test_search` ×3,
  `test_create_recordset`, `test_one2many::test_recomputation_ends`,
  `test_flush_convergence`) y ningún otro de esos cuatro archivos.

Primer gate completo: 10 failed. Seis por `_model_of_records`, tres de la
prueba nueva (forma del atributo y clase de la excepción) y
`test_env_classmethod`, que medía la envoltura sobre `_search_foo`; ahora
lo mide sobre `hr.employee.skill.get_current_skills_by_employee`.

Gate completo de la forma final: **12 613 passed, 66 skipped, 6 xfailed,
0 failed, 5 errors** en 693 s; los 5 errores son los de
`test_multidb_isolation.py` (fixture que exige una base desechable).

Tras el gate, la admisión de estilo pidió partir líneas largas introducidas
(comentarios, docstrings y cinco líneas de prueba) y no añadir una sentencia
`import` en `web/controllers/export.py`, que desplazaba el contexto de
líneas largas heredadas: `env` se toma allí de la misma sentencia de
`orm.models`, que lo reexporta (el mismo objeto). Son cambios sin efecto de
conducta; el subconjunto que los toca (`test_env_classmethod`, la prueba
nueva, `tests/*/web`, `test_one2many` y las dos rejillas de referencia) da
132 passed, 5 skipped (las de referencia, sin árbol montado aquí).

## Pendiente

- Medir el flujo entre funciones (clases devueltas por funciones auxiliares
  como `_inherits_parent`).
- Fijar el accesor de la clase desde un recordset (`type(records)` es lo que
  usa la fuente; preferirlo sobre un nombre nuevo).
