# write-many2many-discards-recompute-0397 — escribir un `Many2many` calculado descarta su recálculo

## Referencia

`odoo19c: odoo/orm/models.py:4469` — `BaseModel.write` escribe cada campo con
`field.write(self, value)`. Para un x2many es `_RelationalMulti.write`
(`odoo19c: odoo/orm/fields_relational.py:737-740`):

    def write(self, records, value):
        # discard recomputation of self on records
        records.env.remove_to_compute(self, records)
        self.write_batch([(records, value)])

## Defecto medido

`BaseModel.write` del consumidor no llama a `field.write` para un
`Many2many`: aparta esos valores con `_pop_many2many_values` y los aplica con
`apply_many2many_commands` (`src/orm/models.py:3088-3100`), que no descarta el
recálculo pendiente. Un `Many2many` calculado, almacenado y editable que
llevaba un cómputo pendiente (el del alta, perezoso) lo ejecuta en el volcado
siguiente y pisa lo escrito.

Sonda (2026-11-22), sobre `account.journal.edi_format_ids`: tras escribir
`[ws]`, la base tenía `[ws]`; tras `flush_all()`, `[ws, plain]`. Durante el
`write` no hubo ni `remove_to_compute` ni `add_to_compute` del campo: la marca
pendiente venía del alta.

## Cambio

En el bucle de `Many2many` de `BaseModel.write`, antes de aplicar los
comandos de cada campo, `env().remove_to_compute(field, self.ids)` — el paso
de `_RelationalMulti.write`. La aplicación de comandos no cambia.

## Prueba

`tests/unit/orm/test_write_many2many_discards_recompute.py`, sobre
`test_orm.compute.onchange.tag_ids` (calculado, almacenado y editable,
`odoo19c: odoo/addons/test_orm/models/test_orm.py:880-937`): el alta deja el
cómputo pendiente, se escribe otra etiqueta, se vuelca y la escrita
sobrevive. Rojo antes del cambio: queda la etiqueta calculada.

| Símbolo | Referencia |
|---|---|
| `BaseModel.write` | `odoo19c: odoo/orm/fields_relational.py:737-740` |

## Segunda mitad, medida al integrar `account-edi-journal-computes-0397`

Descartar el recálculo no bastaba. Leer el campo antes de escribirlo ejecuta
su cómputo perezoso, que deja el valor calculado en caché **y sucio**
(`transaction.field_dirty`). `apply_many2many_commands` escribe la tabla con
el gestor de Django, sin tocar la caché, así que el primer `flush_all`
posterior —el de un `unlink` de otro modelo, por ejemplo— reescribía el valor
calculado sobre el escrito. Sonda: la tabla tenía `[ws]` antes del `unlink` de
los documentos y `[ws, plain]` después; `field_dirty` contenía el diario.

En la fuente `write_real` deja en caché el valor nuevo, y un volcado
posterior es inocuo. Aquí, tras aplicar los comandos, se suelta la marca de
sucio de esas filas y se invalida su caché; la lectura siguiente trae el
valor de la base. El lado inverso (`ManyToManyRel`) no tiene
`_invalidate_cache`: misma guarda que el `_invalidate_cache` del modelo.

Controles de anulación: sin `remove_to_compute` cae sólo
`test_a_written_computed_many2many_survives_the_flush`; sin soltar la marca
ni invalidar cae sólo `test_a_dirty_computed_value_does_not_overwrite_the_written_one`
(y, en el consumidor, `test_removing_a_plain_format_deletes_its_pending_documents`).
