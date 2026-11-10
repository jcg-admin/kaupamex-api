# TASK-API-0511 — `write` anuncia los calculados que escribe

Fecha: 2026-11-09. Hallazgo: H-API-1209 (`kaupamex-docs@34e261328`).
Referencia: odoo-tools `abe4040ec1a45beee90fb694e4eae4453e46b389`,
`odoo19c: odoo/orm/models.py:4401-4493`.

## Contrato de la referencia

Dentro de `with env.protecting(protected, self)`:

1. `self.modified(fnames_modifying_relations, before=True)` (`:4459`);
2. `field.write(self, value)` por campo, en orden de `write_sequence`
   (`:4466-4470`) — `field.write` NO anuncia;
3. `self.modified(vals)` (`:4484`), con el comentario de por qué va
   después de escribir;
4. inversos por grupo (`:4491-4493`).

## Estado de este árbol

El anuncio vive en `FieldDescriptor.__set__` (`src/orm/fields.py`): con
`before=True` para relacionales y después de asignar. Pero los campos de
`protected` (`_protected_while_writing`: inversos y calculados no
`readonly`, con su grupo de `field_computed`) entran en la rama protegida
de `__set__` (`fields.py:1928-1933`), que escribe y retorna **sin
anunciar**. Resultado medido (H-API-1209): escribir `cost` de
`test_orm.model_child_m2o` no recalcula `cost` del padre.

## Decisión

No se reemplaza el anuncio por campo de `__set__` por el global de la
fuente: los campos ordinarios ya se anuncian ahí, y anunciarlos dos veces
duplicaría marcas e invalidaciones. Se anuncia, en `write`, exactamente lo
que `__set__` calla:

- `silenced` = nombres asignados por `setattr` cuyo campo está en
  `protected`;
- antes de asignar: `self.modified(<relacionales de silenced>, before=True)`
  (≙ `:4459` para esos campos);
- después del `save()` y antes de despachar inversos:
  `self.modified(silenced)` (≙ `:4484`, mismo orden respecto de `:4493`).

## Casos (RED)

1. `child.write({'cost': 7})` → tras `flush_model()` el padre tiene
   `cost = 7` en la base (hoy 2). Sin lectura previa de `parent_id`
   (H-API-1210 la enmascara).
2. `write` de un campo ordinario sigue anunciándose una sola vez: espía en
   `_modified` ve el campo una vez, no dos.
3. Un calculado escrito no se recalcula a sí mismo durante el `write` (el
   valor escrito prevalece: `child.cost == 7`, no `len(name)`).
4. Control: escribir `parent.name` sigue marcando `child.size1` (camino
   ordinario, ya verde).

Anulación prevista: retirar el anuncio posterior tumba 1; anunciar todos
los campos (no sólo `silenced`) tumba 2; 3 y 4 no dependen del cambio.

## RED, GREEN y anulación (2026-11-09)

- RED sobre `1b6fde6c`: `1 failed, 3 passed` — cae el caso 1 (el padre
  queda en `cost = 2`); 2, 3 y 4 ya pasaban, como controles.
- GREEN: `4 passed`; con `test_write_multi.py`, `12 passed`.
- Anulación, restaurada y verificada con `cmp`: (a) sin el
  `self.modified(silenced)` posterior → cae exactamente el 1; (b)
  anunciando todos los campos escritos en vez de sólo `silenced` → cae
  exactamente el 2 (el campo ordinario llega dos veces a `_modified`).
