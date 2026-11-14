# Condición x2many cuyo comodelo es un modelo de Django

Creado: 2026-11-14T11:05:41 (UTC). TASK-API-0485. Unidad
`x2many-django-comodel-condition-0485`. La destapó
`hr-applicant-basemodel-0397`: la regla del entrevistador
(`('job_id.interviewer_ids', 'in', user.id)`) revienta con
`AttributeError: type object 'ResUsers' has no attribute 'sudo'` en
`src/orm/fields_relational.py:2550`.

## Búsqueda previa

- `_many2one_condition_to_sql` (`fields_relational.py:2385-2460`) ya tiene
  la rama de un comodelo de Django: `django_comodel_rows` (las filas con sus
  reglas) y `_queryset_subselect`. EXTEND: la misma rama en
  `_multi_condition_to_sql` y en `_multi_get_query_for_condition_value`.
- `tools.query.Query`: `set_result_ids` es lo que `browse(ids)._as_query`
  produce en la fuente; `add_where` admite un `id IN (subselect)`.

Veredicto: EXTEND. GapClass: A (bloquea una regla de seguridad de la
fuente). ExecuteNow: yes.

## Contrato (`odoo19c: odoo/orm/fields_relational.py:779-837`)

`_RelationalMulti.condition_to_sql`: `in`/`not in` → `any`/`not any`;
una colección de ids se vuelve `comodel.browse(ids)._as_query()` (en sudo,
sin `active_test`), `False` en la colección parte la condición, un `SQL`
se envuelve en `('id', 'any', sql)`, y un dominio va a
`comodel._search(domain & field_domain)`. La fuente no tiene comodelos
que no sean `BaseModel`: la rama es adaptación declarada, igual que la del
`Many2one`.

## Medido aquí (`d07be908`)

- 0 modelos `BaseModel` con un Many2many concreto hacia un modelo que no lo
  es (recorrido de `apps.get_models()`): la rama nunca se ejercitó.
  `hr.applicant.interviewer_ids` → `res.users` es el primero.
- `model.env['res.users']` devuelve la clase de Django: no tiene `sudo`,
  `browse` ni `_search`.

## Decisión

Con un comodelo sin `_from_ids` (la misma prueba que usa el `Many2one`):

- colección de ids → `Query` del comodelo con `set_result_ids(ids)`;
- `False` en la colección → todas las filas (`_base_manager`);
- dominio → `django_comodel_rows(comodel, domain & field_domain, bypass)`,
  envuelto en un `Query` con `id IN (subselect)`;
- `Query` con dominio de campo no vacío → el mismo `id IN (subselect)`.

## RED y anulación

Modelo de sonda `BaseModel` con un Many2many hacia un modelo de Django de
sonda: `search([('tags', 'in', [id])])`, `not in`, `in [False]` y
`('tags', 'any', [('name', '=', x)])` devuelven las filas esperadas.
Anulación: sin la rama vuelve el `AttributeError` en los cuatro casos.
