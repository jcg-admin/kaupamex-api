# Gemelo en `write` del check de `bypass_search_access` (TASK-API-0422)

Sucesor obligatorio de `orm-create-bypass-search-access-check-0422`.

## Referencia

`odoo19c: odoo/orm/fields_relational.py:407-411`, en `Many2one.write`, antes
de filtrar los registros que no cambian:

```python
if self.bypass_search_access and not records.env.su:
    try:
        records.env[self.comodel_name].browse(cache_value).check_access('read')
    except AccessError as e:
        raise AccessError(records.env._("Failed to write field %s", self) + "\n" + str(e)) from e
```

## Puerto

- `ForeignKey` no tiene `write` propio: usa `_field_write` (`fields.py:4862`).
- `BaseModel.write` no pasa por `Field.write` para una FK: asigna fila por fila
  en `RecordLoaderMixin.write` (`models.py:3070`).
- El check de `create` vive hoy en `models.py` (`_check_bypassed_comodel_read`).

## Contrato

Funciones cuyo cuerpo cambia:

- `src/orm/fields_relational.py`: NUEVA `check_bypassed_comodel_read(field,
  value)` (pública porque la usa `models.py`; mismo cuerpo que el helper de
  `create`), NUEVA `_check_many2one_write_access(field, value)` que la envuelve
  con el mensaje verbatim, y NUEVO `_many2one_write(self, records, value)`
  instalado como `models.ForeignKey.write`: el check (si `bypass_search_access`
  y no `is_su()`) y después `_field_write`.
- `src/orm/models.py`: `RecordLoaderMixin.write` comprueba cada FK de `values`
  con `_check_many2one_write_access` antes de escribir nada;
  `DefaultGetMixin.create` usa `check_bypassed_comodel_read` importado; se
  retira el helper local `_check_bypassed_comodel_read`.

Pruebas (`tests/unit/orm/test_write_bypass_search_access.py`, mismas sondas
que la prueba de `create`): 1) `write` no-su con un registro ilegible levanta
`AccessError` cuyo mensaje empieza por `Failed to write field` y la fila no
cambia; 2) con un id entero, igual; 3) `field.write(records, value)` directo
levanta; 4) bajo `sudo()` pasa; 5) sin la bandera pasa; 6) `None` y un
registro legible pasan.

Anulación: sin la llamada en `RecordLoaderMixin.write` caen 1 y 2; sin el
check en `_many2one_write` cae 3.

## Corrección medida (implementación)

La comprobación en `RecordLoaderMixin.write` sobraba: con ella anulada los seis
casos seguían verdes, porque la escritura de una fila acaba pasando por
`ForeignKey.write`. Se retira; queda un solo sitio, `_many2one_write`, el mismo
que la fuente (`Many2one.write`). Anularlo tumba exactamente 1, 2 y 3.

El modo superusuario se lee del `env` de los registros (`records.env.su`, como
la fuente), con `is_su()` como respaldo para una fila de Django sin `env`
(`_records_su`): con `is_su()` a secas, `foo.sudo().write(...)` rehusaba.

Funciones cuyo cuerpo cambia: en `src/orm/fields_relational.py`,
`check_bypassed_comodel_read`, `_records_su`, `_check_many2one_write_access` y
`_many2one_write` (nuevas); en `src/orm/models.py`, `DefaultGetMixin.create`
importa el helper y se retira el local `_check_bypassed_comodel_read`.
