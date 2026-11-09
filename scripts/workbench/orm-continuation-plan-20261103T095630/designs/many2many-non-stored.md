# Diseño — `Many2many` sin columna (TASK-API-0485)

Fecha: 2026-11-09T02:05:21. Bloquea el cierre de las dos búsquedas abiertas del contrato de
grupos implicados (`designs/res-groups-implied-contract.md`).

## Contrato (odoo19c)

Un `fields.Many2many(compute=..., search=...)` sin `store` no tiene tabla
intermedia: se calcula al leer (`compute`) y se busca por su método
(`search`), que devuelve un dominio. Casos de la referencia que lo usan aquí:
`res.groups.all_implied_ids`, `all_implied_by_ids` (`res_groups.py:71-78`),
`res.users.all_group_ids` (`res_users.py:258`).

## Aquí (medido)

- `orm.fields_relational.Many2many` construye siempre un
  `ManyToManyField`, y su docstring declara que no admite `store=False`.
- Los campos escalares sin columna se contribuyen con `private_only=True`
  (`orm/fields.py`, `_field_contribute_to_class`); un `ManyToManyField`
  crea además su modelo intermedio en `contribute_to_class`
  (`django/db/models/fields/related.py`), así que esa vía sola no basta.
- Hoy las tres clausuras son `@property` y sus `_search_*` tienen otra
  firma (`group_ids, negate` → queryset), llamados sólo desde
  `tests/integration/base/test_res_groups_port.py`.

## Qué hay que medir antes de RED

1. Si `ManyToManyField` con `private_only=True` y un `through` inexistente
   llega a registrar el modelo intermedio (sonda en banco).
2. Cómo traduce `orm.domains` un campo sin columna con `search=` (los
   escalares de `analytic_line.py:216` y `ir_actions_report.py:458`): si la
   rama vale para un relacional.
3. Qué consumidores leen hoy `all_implied_ids` como queryset (la propiedad
   devuelve una lista/queryset; un campo devolvería un recordset).

## Criterio de cierre

Los dos escenarios `OPEN` del contrato de grupos pasan a coincidir y se
retiran de `OPEN`; los `_search_*` toman la firma `(operator, value)` →
dominio de la referencia.

## Mediciones 1 y 2 (2026-11-09)

1. `ManyToManyField('base.ResGroups').contribute_to_class(Host, 'probe_ids',
   private_only=True)` sobre un modelo de sonda **sí registra** el modelo
   intermedio `test_orm.ProbeHost_probe_ids` y deja el campo en
   `_meta.many_to_many`: la vía de los escalares no basta, y el campo crearía
   tabla y migración. El M2M sin columna necesita su propio campo (sin
   `through` automático) o un descriptor que publique un campo en el registro
   sin pasar por `contribute_to_class` de Django.
2. `orm.domains` ya despacha `field.search` por `determine_domain`
   (`domains.py:1113-1175, 1237`): si el campo está en
   `model_field_registry` con `search`, la búsqueda tiene ruta. El
   `ValueError` actual sale de `__get_field` (`domains.py:1102`), que no
   encuentra el nombre.

Siguiente paso: la medición 3 (consumidores de `all_implied_ids` como
queryset) y la elección entre las dos formas del punto 1.

## Medición 3

`git grep -n "\.all_implied_ids\|\.all_implied_by_ids\|\.all_group_ids" --
src addons ':!*tests*'`: **20** lecturas; **4** usan API de queryset sobre el
valor (`values_list` ×3, `exclude` ×1). El campo nuevo tiene que devolver
algo que admita esas cuatro, o se adaptan esos consumidores en el mismo
pase.

## Contrato de los consumidores, leído en odoo-tools@abe4040ec1 (2026-11-09T05:07:23)

- `res.groups.all_implied_ids` (`odoo/addons/base/models/res_groups.py:71-72`): `Many2many('res.groups',
  recursive=True, compute='_compute_all_implied_ids', compute_sudo=True, search='_search_all_implied_ids')`.
  El cómputo (`:246-250`) asigna `g.ids + get_superset_ids(g.ids)`: clausura **reflexiva** y transitiva.
  La búsqueda (`:252-258`) sólo atiende `in`/`not in` y devuelve `[('id', op, value + get_subset_ids(value))]`;
  cualquier otro operador, `NotImplemented`.
- `all_implied_by_ids` (`:76-77`, `:261-280`): el simétrico, con `get_subset_ids` al computar y
  `get_superset_ids` al buscar; además traduce `any`/`not any` con un `Domain` a `in`/`not in` buscando antes.

## Decisión de forma

Una clase propia, `NonStoredMany2many`, con el mismo protocolo que el `One2many` declarado: se contribuye
sin entrar en `_meta` (no crea tabla intermedia ni migración), y la recogen `non_stored_fields` (registro
`_fields`) y `_non_stored_field` (resolución de dominios). La fachada `Many2many(...)` la devuelve sólo
cuando `store=False` (explícito o implicado por `compute=` sin `store`). En los demás casos devuelve
el `ManyToManyField` de siempre.

Esto diverge de la nota «`store` es un atributo, no un tipo» (`odoo19c: odoo/orm/fields.py:455`) por un
motivo medido: `ManyToManyField.contribute_to_class` registra el modelo intermedio incluso con
`private_only=True` (medición 1). El precedente es el `One2many`, que ya es una clase propia por la
misma razón.

Protocolo de la clase:
- atributos de campo: `name`, `model_name`, `comodel_name`, `type='many2many'`, `store=False`,
  `compute`, `compute_sudo`, `search`, `recursive`, `string`, `readonly=True`, `relational=True`;
- lectura: llama al método de cómputo una vez por fila (en `sudo` si `compute_sudo`) y devuelve un
  queryset del comodelo filtrado por los ids calculados. Así admite `values_list`/`exclude`, los 4
  consumidores de la medición 3;
- asignación (desde el cómputo): admite ids, filas o querysets, y guarda los ids en la caché de la fila;
- búsqueda: `determine_domain` (heredado del patrón de `models.Field`) llama al método `search` con
  `(operator, value)`.

Los `_search_*` de `res.groups` pasan a la firma de la referencia `(operator, value)` → dominio. Su
consumidor actual (`tests/integration/base/test_res_groups_port.py`) se adapta en el mismo pase.

Criterio de cierre: los dos escenarios `OPEN` de `test_contract_res_groups_implied_reference.py` coinciden
y salen de `OPEN`; controles: sin la rama de `_non_stored_field` la búsqueda vuelve a fallar; sin el cómputo
reflexivo cambia el resultado.

## Corrección de la decisión de forma (2026-11-09T05:08:39) — REUSE, no una clase nueva

La decisión de arriba se basó en la medición 1, que sondeó `ManyToManyField.contribute_to_class` de Django
directamente y **no** la costura del árbol. Medido después sobre `apps.get_models()`: ya existen `Many2many`
con `store=False` y `remote_field.through is None` (`base.IrActionsServer.available_model_ids`,
`base_install_request.BaseModuleInstallRequest.user_ids`, `…Review.module_ids`,
`sale.SaleOrder.duplicated_order_ids`). Los resuelve `_field_contribute_to_class` (`src/orm/fields.py`):
`private_only` cuando `store is False` y `serialize=False`. Su lectura es la del descriptor de campo
calculado, y `tests/unit/orm/test_bare_store_false_declaration.py` cubre su forma.

Decisión vigente: **REUSE**. `all_implied_ids`, `all_implied_by_ids` y `all_group_ids` se declaran con la
fachada `fields.Many2many(..., compute=..., compute_sudo=True, search=..., store=False)` como en la referencia.
Sus `_search_*` toman la firma `(operator, value)` y devuelven dominio. La clase `NonStoredMany2many` **no
se construye**. El cómputo asigna un queryset del comodelo, así que `values_list`/`exclude` siguen sirviendo
a los 4 consumidores de la medición 3.

## Verificación

- RED previo: los dos escenarios `OPEN` de `test_contract_res_groups_implied_reference.py`. Ahora coinciden
  y `OPEN` queda vacío.
- Dependencias de la referencia: `@api.depends('implied_ids.all_implied_ids')`,
  `('implied_by_ids.all_implied_by_ids')` y `('group_ids.all_implied_ids')` (`res_groups.py:245,260`,
  `res_users.py:446`).
- El valor calculado vive en la caché del entorno. El manager M2M de Django no pasa por `write`, así que los
  receptores de `m2m_changed` existentes invalidan `all_group_ids` de los usuarios afectados y, en un cambio
  del grafo, las tres clausuras.
- `test_a_raw_write_…`: tras un `INSERT` crudo, el campo se lee después de invalidar su caché, como en la
  referencia. El memo de `_get_group_ids` sigue ciego, que es lo que el caso mide.
- Controles: sin `search=` en `all_implied_ids` cae la comparación con la referencia; sin la invalidación del
  receptor caen los dos casos de alta y baja de grupo.
- Consumidores (`tests/integration/base`, `tests/unit/{base,authz_timeout,orm,bus,sale}`,
  `tests/integration/test_orm`): pasan.
