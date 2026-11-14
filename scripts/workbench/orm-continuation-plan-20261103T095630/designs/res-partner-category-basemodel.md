# res.partner.category sobre BaseModel

Unidad: `basemodel-adoption-res-partner-category-0397` (TASK-API-0397).

## Contrato medido en la referencia

`odoo19c: odoo/addons/base/models/res_partner.py:139-181`
(`models.Model`, `_parent_store = True`):

| Símbolo | Línea | Aquí antes | Aquí después |
|---|---|---|---|
| clase sobre `models.Model` | :139 | `TimeStampedModel` | `models.BaseModel, TimeStampedModel` |
| `color` default `_get_default_color` | :145-149 | `default=0` y `save()` siembra al crear | `default=_get_default_color` en el campo |
| `parent_id` Many2one, `index`, cascade | :150 | campo `parent` (attname y columna `parent_id`) | igual: el nombre del campo es de la unidad de nombres de FK |
| `child_ids` One2many | :151 | `related_name='child_ids'` | igual |
| `partner_ids` Many2many, `column1='category_id'`, `column2='partner_id'` | :154 | campo `partners`, tabla `res_partner_category_partners` | `partner_ids`, tabla `res_partner_res_partner_category_rel` |
| `_check_parent_id` con `_has_cycle` | :156-159 | recorrido propio en `save()` | `@api.constrains('parent_id')` con `_has_cycle` |
| `_compute_display_name` | :161-172 | igual | recorre `parent_id` |

`BaseModel` mantiene el árbol con `_parent_name = 'parent_id'`, y lo
resuelve por el attname del FK `parent`: es lo que ya hace `hr.department`.
Renombrar el campo a `parent_id` no es condición de la adopción; queda en
la unidad de nombres de FK, con el resto de los FK de `base`.

El camino de Django (`objects.create`, `save()`) sigue el patrón de
`hr.department` e `ir.ui.menu`: una fila que cambia de padre delega en
`orm.models._parent_store_update`; una nueva calcula su propia ruta.

Fuera de esta unidad, declarado: `name` con `required=True` y
`translate=True` (`:148`). El almacenamiento jsonb de `translate=True` es
TASK-GEN-0060.

## Casos (RED)

1. el modelo deriva de `BaseModel`;
2. `create` del ORM reparte un color entre 1 y 11;
3. `write` de `parent_id` reescribe la ruta de todo el subárbol;
4. un ciclo por `write` lo rechaza `_parent_store_update` con
   `UserError("Recursion Detected.")`, antes que la restricción, como en
   la fuente (`odoo/orm/models.py:5030`);
5. `partner_ids` vive en la tabla y las columnas de la fuente.

## Anulación

- retirar el `default` del color: cae el caso 2;
- retirar la delegación de `save()` en `_parent_store_update`: cae el
  caso 3 por el camino de Django.
- `_check_parent_id` se porta con `_has_cycle` aunque ningún `write` la
  alcance con `_parent_store`; por eso no tiene anulación propia.

## Lo que destapó la adopción

1. **`_compute_display_name` no terminaba.** Recorría
   `while current is not None`; sobre `BaseModel` el padre vacío es un
   recordset vacío, nunca `None`. Es el cuelgue del primer intento. Pasa al
   `while current:` de la fuente (`:169`).
2. **El ciclo quedaba persistido por el camino de Django.** `save()`
   escribía la fila y después `_parent_store_update` rechazaba la
   recursión. Ahora `save()` va en una transacción, como el `write` de la
   fuente.
3. **El atajo de `parent_path` no se aplicaba a ningún `BaseModel` con el
   FK llamado `parent`.** `_operator_child_of_domain` y
   `_operator_parent_of_domain` comparaban `parent == _parent_name`
   literal, y `BaseModel` declara `'parent_id'` (el attname). Nuevo
   `orm.model_classes.is_parent_field`: es el padre si resuelve al mismo
   campo.
4. **Dos pruebas de `One2many` usaban la categoría como modelo de Django.**
   Pasan a `ir.module.category`, que sigue siéndolo.

## Medición

- 5 de 5 casos nuevos; 16 de 16 en `test_res_partner_category.py`; los diez
  archivos consumidores en verde.
- Anular el `default` del color: caen exactamente los dos casos del color.
- Anular la transacción de `save()`: cae exactamente `test_a_cycle_is_refused`.
- Anular `is_parent_field` (comparación literal): caen exactamente las dos
  pruebas del atajo en `test_domain_hierarchy.py`.
