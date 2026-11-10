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

## Contrato completo de `modified` en `write` (2026-11-10)

Derivado de `odoo19c: odoo/orm/models.py:4397-4493` (odoo-tools
`abe4040ec1`) y comparado con `RecordLoaderMixin.write` en `api@2c5736b3`:

| Paso de la fuente | Línea | Aquí | Prueba |
|---|---|---|---|
| `protected` = grupo `field_computed` de cada campo con inverse o calculado editable | `:4419-4429` | `_protected_while_writing` | `test_compute_onchange.py::test_write` |
| fuerza el cálculo de los hermanos del grupo que no se asignan (`to_compute`) | `:4430-4437` | `models.py:2990-2997` | **`test_shared_compute.py::test_writing_one_sibling_keeps_the_pending_recompute_of_the_other`** |
| `modified(fnames_modifying_relations, before=True)` | `:4460` | `models.py:3037-3044` | suites de x2many inverso |
| `field.write` por `write_sequence` | `:4466-4467` | descriptores con `WRITING_VALUES`; x2many al final (`write_sequence` 20) | `test_compute_onchange.py` |
| `modified(vals)` una vez, tras escribir | `:4482` | final de `write` (este diseño) | `test_an_ordinary_field_is_announced_once`, `test_writing_a_computed_field_recomputes_its_dependents` |
| los descriptores no anuncian dentro de `write` | `fields.py:1807-1843` (sólo fuera de `write`) | `FieldDescriptor.__set__` omite el anuncio con `WRITING_VALUES` | `test_an_ordinary_field_is_announced_once` |
| `new()`: `modified(before=True)` + `write` + `modified` bajo `protecting` | `fields.py:1825-1832` | `_many2many_descriptor_set` y la rama `NewId` del descriptor | `test_compute_onchange.py::test_set_new` |

**El escenario de un hermano pendiente.** `test_orm.shared.compute`
(`test_orm.py:2454-2476`, portado con la migración `0045`): `name` deja
`start` y `end` pendientes; escribir sólo `start` antes del volcado tiene
que calcular `end` desde `name` (25) y conservar el `start` escrito (7). Sin
el paso `to_compute`, `end` no se calcula dentro de la protección y la
prueba cae. Control de anulación: con `if False and to_compute` cae
exactamente esa prueba de las 17 de `test_shared_compute.py`,
`test_write_announces_computed.py` y `test_compute_onchange.py`.

**Relación con `_write`/`_write_multi`/`_flush` (TASK-API-0510).** La
persistencia sigue siendo `save(update_fields=...)` de Django por fila, no el
`_write_multi` de la fuente; los dos `xfail(strict=True)` de SQL siguen con
TASK-API-0510. Los anuncios no dependen de esa diferencia: ocurren antes del
volcado, sobre la caché y las marcas de recómputo de la transacción.

Regresión del subconjunto derivado (los directorios que recorren el
registro de modelos más `test_orm`): `tests/integration/test_orm`,
`tests/unit/orm`, `tests/unit/base`, `tests/integration/base`,
`tests/unit/account`, `tests/unit/onboarding`, `tests/unit/product`,
`tests/unit/scripts` → **6969 passed, 65 skipped, 6 xfailed, 0 failed**.

*Métrica:* valores en la base tras `flush_model`, y campos que llegan a
`_modified`. *Ciega a:* el orden relativo de los anuncios entre campos de un
mismo `write` (sólo se mide que cada uno ocurra una vez), y a escrituras por
lotes de varios registros con valores distintos, que la fuente no tiene en
`write` (es `write` sobre un recordset con un solo `vals`).
