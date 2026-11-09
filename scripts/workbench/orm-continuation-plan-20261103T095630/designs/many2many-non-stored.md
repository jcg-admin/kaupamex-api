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
