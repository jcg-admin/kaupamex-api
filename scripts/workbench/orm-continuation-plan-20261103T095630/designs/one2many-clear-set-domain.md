# `SET`/`CLEAR` de un One2many respetan el dominio del campo

Unidad: `account-journal-payment-method-lines-0515` (lo destapa) sobre
`src/orm/commands.py`. Fecha: 2026-11-17.

## Defecto medido

`AccountJournal` declara dos One2many sobre el mismo `Many2one` inverso
(`account.payment.method.line.journal_id`), separados por dominio
(`payment_type = inbound` / `outbound`). El cómputo de cada uno empieza con
`Command.clear()`. Aquí, calcular el saliente desenlaza también la línea
entrante: `_apply_one2many_triples` borra o desenlaza **todas** las filas
del inverso (`current_ids()` sin dominio). La prueba
`test_unlinking_a_journal_removes_its_payment_method_lines` lo mostró: tras
leer entrante y saliente, la línea entrante queda con `journal_id` nulo.

La prueba previa `test_a_bank_journal_gets_one_manual_line_each_way` pasaba
porque leía el valor en caché; no discrimina y se refuerza leyendo la base.

## Contrato de la referencia

`One2many.write_real`, rama almacenada
(`odoo19c: odoo/orm/fields_relational.py:1027-1043`):

```python
lines = comodel.browse(line_ids)
domain = self.get_comodel_domain(model) & Domain(inverse, 'in', recs.ids) \
    & Domain('id', 'not in', lines.ids)
unlink(comodel.search(domain))
lines[inverse] = recs[-1]
```

Lo que se retira es lo que cumple el dominio del campo, pertenece al
registro y no está en la lista nueva. Una línea del mismo inverso que no
cumple el dominio no se toca.

## Cambio

- `apply_one2many_commands(record, rel, value, create=False, domain=None)` y
  `_apply_one2many_triples(..., domain)`: en `SET`/`CLEAR` las filas a
  retirar son las del inverso que además cumplen `domain`
  (`domain._to_q(comodel)` sobre el `_base_manager`, que sirve a un comodelo
  `BaseModel` y a uno de Django). Sin `domain` el comportamiento no cambia.
- `One2many.write_real` y `One2many.__set__` (`src/orm/fields_relational.py`)
  pasan `_multi_comodel_domain(self, record)`, el `Domain` de
  `get_comodel_domain`.
- Los sitios de `src/orm/models.py` no cambian: dos son de creación
  (`allow_full_delete` falso: no retiran nada) y dos reciben la relación
  inversa de Django, que no declara dominio.
- Se retira la nota `pendiente: el domain del One2many` del docstring; queda
  pendiente el `context` del campo.

## Pruebas

`tests/unit/orm/test_one2many_clear_respects_domain.py`, sobre
`test_orm.discussion` (`messages`, `important_messages` con dominio
`important = True`):

| Caso | Espera |
|---|---|
| `important_messages = [Command.clear()]` con una línea llana y una importante | la importante se retira; la llana sigue enlazada |
| `important_messages = [Command.set([otra])]` | sólo las importantes fuera de la lista se retiran |
| `messages = [Command.clear()]` (sin dominio) | se retiran todas |

Anulación: quitar el filtro de dominio hace caer los dos primeros casos y no
el tercero.

Y `tests/unit/account/test_journal_payment_method_lines.py` lee las líneas
del diario desde la base.

*Métrica:* filas del comodelo con el inverso apuntando al registro, leídas
de la base tras la escritura.
*Ciega a:* el `context` del campo y la rama no almacenada de `write_real`.
