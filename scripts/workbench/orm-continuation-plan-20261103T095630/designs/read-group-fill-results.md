# Unidad 6a — `_read_group_expand_full` y `_read_group_fill_results`

Autoridad: `odoo19c: odoo/orm/models.py:2310-2385` (odoo-tools
`abe4040ec1a45beee90fb694e4eae4453e46b389`) y
`odoo19c: odoo/orm/fields_selection.py:85-91` (`Selection._get_attrs`).

## Contrato medido en la referencia

- `_read_group_expand_full(groups, domain)` → `groups.search([])`: todos los
  registros del comodelo, en su orden.
- `_read_group_fill_results(domain, groupby, annoted_aggregates,
  read_group_result, read_group_order=None)`:
  1. el nombre de campo es `groupby.split('.')[0].split(':')[0]`; sin
     `field.group_expand` devuelve la entrada intacta;
  2. `group_expand` es invocable o el nombre de un método del modelo;
  3. relacional: los grupos presentes se convierten en registros del
     comodelo, `group_expand(self, groups, domain).sudo()` da el universo;
     clave = `id`;
  4. no relacional: `group_expand(self, values, domain)`; con
     `read_group_order == groupby + ' desc'` la lista se invierte en sitio;
     clave = el valor;
  5. fusión: el orden lo da el universo; cada valor ausente toma un elemento
     vacío construido con `_read_group_empty_value` por agregado; los
     resultados cuya clave no está en el universo se añaden al final;
  6. relacional con `groups._fold_name` entre los campos del comodelo: cada
     línea recibe `__fold`.
- Rama `desc` relacional: la referencia escribe
  `values.browse(reversed(values._ids))` **sin reasignar**; el orden no
  cambia. Se porta igual: corregirlo alteraría la conducta medida.
- `Selection(group_expand=True)` → `_default_group_expand` (un grupo por
  opción, en el orden declarado). En Kaupamex el método existía y el mapeo
  `True` → método no: `group_expand=True` quedaba como `True`, que no es
  invocable.

## Adaptaciones declaradas (no cambian la conducta)

| Referencia | Kaupamex | Razón |
|---|---|---|
| `getattr(self.env.registry[self._name], name)` | `getattr(type(self), name)` | `env.registry` es aquí un módulo; la clase del registro es `type(self)` |
| `self.env[comodel].browse(ids)` | `_read_group_recordset(self.env, self.env[comodel], ids, ids)` | `env[name]` devuelve la clase; un comodelo de Django no tiene `_from_ids` |
| `.sudo()` | se llama si el resultado lo ofrece | un `QuerySet` de Django no tiene `sudo`; ya se lee sin reglas |
| `groups._fold_name in groups._fields` | ídem, con `getattr` | un `QuerySet` de Django no declara `_fold_name` |

## Casos de prueba (`tests/unit/orm/test_read_group_fill_results.py`)

1. sin `group_expand` → la misma lista;
2. Many2one con invocable → todos los grupos del universo, vacíos con
   `count` 0 y `sum` False, en el orden del universo;
3. `group_expand` por nombre de método;
4. clave fuera del universo → al final;
5. no relacional con lista y `desc` → invertida;
6. `__fold` cuando el comodelo declara el campo de plegado;
7. `_read_group_expand_full` → `groups.search([])`;
8. `Selection(group_expand=True)` resuelve a `_default_group_expand`.

Control de anulación previsto: retirar el bloque de fusión de los ausentes
(caen 2, 3, 5) y retirar el mapeo de `Selection` (cae 8).

*Métrica:* listas de dicts devueltas sobre filas sembradas.
*Ciega a:* `read_group`/`formatted_read_group` de web, que consumen esto
(unidad 6b).
