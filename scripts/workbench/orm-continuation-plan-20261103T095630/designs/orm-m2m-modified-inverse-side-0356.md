# TASK-GEN-0356 (prerrequisito) — avisar al lado inverso de un Many2many

Fuente: `odoo19c: odoo/orm/fields_relational.py:1586-1593`, al final de
`Many2many.write_real`:

```python
if modified_corecord_ids:
    corecords = comodel.browse(modified_corecord_ids)
    corecords.modified([
        invf.name
        for invf in model.pool.field_inverses[self]
        if invf.model_name == self.comodel_name
    ])
```

Decisión del orquestador del 2026-11-25 para 0356 (borrador
`research/base-res-users-share-field-0356.md`, punto 2): `ResUsers.share` no
se rodea con un marcado propio; el motor avisa al lado inverso como la fuente,
y 0356 depende de esta unidad.

## Estado del puerto

`_notify_m2m_modified` (`src/orm/models.py:5226-5275`) recibe la señal
`m2m_changed` del manager de Django, que es por donde escribe
`_many2many_write_relation` (`src/orm/fields_relational.py:3297`). Avisa sólo
al **dueño** del campo que cambió (`record.modified([field.name])`). Ningún
camino llama `modified` sobre los registros del comodelo con los campos de
`field_inverses[field]`. El lado inverso sí se mantiene en caché
(`fields_relational.py:3348-3360`), pero la caché no es el aviso: un calculado
almacenado del comodelo que dependa del inverso queda sin recomputar.

## Contrato

Tras `post_add`, `post_remove` y `post_clear`, por cada campo `field` del dueño
cuya tabla es `sender`:

- `corecords` = los ids del **otro** lado que cambiaron: `pk_set` cuando la
  señal viene del lado directo; la instancia cuando viene del inverso; en un
  `clear`, los que tenía antes (ya se recuerdan en `pre_clear`).
- se llama `corecords.modified([invf.name for invf in field_inverses[field]
  if invf.model_name == field.comodel_name])` — el filtro de la fuente.

Un Many2many simétrico (`symmetrical=True`) es su propio inverso y ya avisa
a los dos extremos: no se duplica.

## Casos (RED), `tests/unit/orm/test_m2m_modified_inverse_side.py`

Con `test_orm.user` (`group_count` almacenado, `@depends('group_ids')`) y
`test_orm.group.user_ids`, su inverso sobre la misma tabla:

1. enlazar un usuario desde el grupo (`group.write({'user_ids':
   [Command.link(user.id)]})`) recalcula `user.group_count` a 1, leído de la
   base;
2. desenlazarlo (`Command.unlink`) lo vuelve a 0;
3. `Command.clear()` desde el grupo lo vuelve a 0;
4. control: escribir desde el usuario (`user.write({'group_ids': …})`) ya
   recalculaba antes de esta unidad.

## Anulación prevista

Sin el aviso al comodelo caen 1, 2 y 3; el 4 sobrevive.

## Addendum — premisa refutada: REUSE (2026-11-25)

Los cuatro casos pasan sin implementar nada. El puerto ya cumple el contrato
de `:1586-1593` por otra vía: `_notify_m2m_modified` avisa al dueño
(`group.modified(['user_ids'])`) y `_modified_triggers` baja por
`registry.field_inverses` (`src/orm/models.py:5093`) hasta los dependientes
del inverso, que es donde vive `test_orm.user.group_count`.

Control de anulación, medido: con `_notify_m2m_modified` reducido a `return`
caen los cuatro casos; restaurado, pasan los cuatro (`cmp` contra la copia).

La primera versión de los casos **no discriminaba**: sin señal sólo caía
`remove`. El usuario recién creado dejaba pendiente el cómputo de
`group_count` y el `flush_all` final lo resolvía leyendo la relación actual,
con o sin aviso (sub-patrón D). El fixture ahora vuelca y verifica `0` antes
de escribir.

Veredicto: **REUSE**. Esta unidad no implementa nada; los casos quedan como
regresión del contrato. Para 0356 la dependencia está satisfecha por el
mecanismo existente.
