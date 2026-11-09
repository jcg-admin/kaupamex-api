# Análisis — ramas de `Field.setup_related` (TASK-API-0485)

Fecha: 2026-11-09T01:13:14. Referencia `odoo19c: odoo/orm/fields.py:604-664`; porte
`src/orm/fields.py` (`_field_setup_related`, `walk_related_chain`).

## Rama por rama

| Rama de la fuente | Aquí | Estado |
|---|---|---|
| cadena por `model.pool`, `KeyError` si falta un eslabón (`:608-615`) | `walk_related_chain` sobre `model_field_registry` | portada |
| `field.setup()` de cada eslabón no montado (`:617-618`) | el barrido perezoso `ensure_field_setup` monta todos los marcados antes | divergencia de mecanismo, efecto igual |
| tipo coherente o `TypeError` (`:622-624`) | igual | portada |
| `related_field` (`:626`) | igual | portada |
| `field_setup_dependents.add` (`:629`) | **no se inscribe**; el colector existe (`registry.py:1939`) | sin receptor: su único consumidor, el re-montaje de dependientes al reconstruir un campo (`registry.py:479`), no existe aquí porque las clases de Django no se reconstruyen (`_setup_models__`). Llenarlo no cambiaría conducta |
| `compute`, `inverse`, `search` (`:632-637`) | igual | portada |
| aviso de default redundante (`:641-642`) | igual | portada |
| `related_attrs` (`:645-649`) | igual | portada |
| `_extra_keys__` con `_valid_field_parameter` (`:651-653`) | no se copia | sin sujeto: medido, las únicas claves extra de este árbol son argumentos de Django (`rel`, `to`, `related_name`, `on_delete`…); copiar `related_name` a un related rompería los accesores inversos. La fuente sólo copia lo que `_valid_field_parameter` admite |
| caso `inherited`: `inherited_field`, `required`, `_modules` (`:656-664`) | igual | portada |

## Mediciones

- Con `ensure_field_setup()` forzado (6245 campos montados): **53** campos
  `related=` declarados no heredados, **49** con `related_field`.
- Los **4** restantes son `One2many` declarados (`fields_relational.One2many`):
  `res.company.bank_ids`, `test_orm.multi.partners`,
  `test_orm.related.foo_foo_ids` y `foo_foo_sudo_ids`. No son campos de
  Django ni pasan por el barrido; resuelven su `related` con su propio
  `_get_related`/`_set_related`. Queda abierto si su búsqueda
  (`_search_related`) está cubierta.
- Una primera medición dio 0 de 53: no forzaba el barrido perezoso. Sesgo
  del instrumento, no del código.

## Corrección de esta unidad

El comentario de `fields.py` («`_extra_keys__` y `_modules` … divergencia
de mecanismo declarada») es falso para `_modules`, que el propio
`setup_related` porta. Se corrige con la tabla de arriba.

## Cerrado en el mismo pase

- Búsqueda por un `One2many` declarado con `related=`: sonda sobre
  `test_orm.related.foo_foo_ids` (`foo_id.foo_ids`) con dos registros `a`, `b`
  del mismo `foo`: leer da `[a, b]` y `search([('foo_foo_ids', 'in', [b])])`
  da `[a, b]`, que es la semántica de la cadena. Sin divergencia observada.
