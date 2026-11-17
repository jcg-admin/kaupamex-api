# Many2many de un registro `new()` hacia un comodelo de Django — flujo

Unidad `orm-many2many-django-comodel-new-0485`. Commit de código
`aebe13c4`. Este diseño se escribió **después** de ese commit: el gate
`scripts/check_reference_flow.py`, aplicado retroactivamente, lo rechaza
(`_django_comodel_rows`, `_many2many_descriptor_set`,
`_x2many_descriptor_get` y `_RelationalMulti.write_batch` cambiaron sin
diseño). Es el defecto que la instrucción 4.3.2 nombra, cometido aquí.

Referencia: `odoo-tools` en `abe4040ec1`.

## Flujo de la referencia (medido)

| Paso | Evidencia |
|---|---|
| Entrada | `record.m2m = valor` → `Field.__set__`, cubo de ids nuevos: `odoo19c: odoo/orm/fields.py:1824-1831` — protege los calculados del campo, `modified(before=True)` por ser relacional, `write`, `modified` |
| Escritura | `_RelationalMulti.write` (`:737`) descarta el recálculo y llama a `write_batch` (`:742-764`), que normaliza a comandos: tupla → `SET`, recordset → `SET`, `False`/`None` → `CLEAR`, lista de ids → `SET`; ids nuevos → `write_new` |
| Estado | `Many2many.write_new`, `odoo19c: odoo/orm/fields_relational.py:1596-1660`: `old_relation` es el valor ACTUAL (`record[self.name]._ids`, `:1607`); los comandos se aplican sobre él; el resultado se escribe con `_update_cache` (`:1648`) y se actualiza el inverso |
| Inicialización | `new(vals)` → `_update_cache` → `_RelationalMulti.convert_to_cache` (`:589-636`), que parte de `()` sin origen (`:611`): coincide con el valor actual, que en `new()` es vacío |
| Lectura | `Field.__get__` (`odoo19c: odoo/orm/fields.py:1642-1673`): acierto de caché → `convert_to_record` |
| Persistencia | ninguna: el registro es nuevo |

## Stack y Consumer

- La caché de un `Many2many` hacia un modelo de Django guarda un
  `QuerySet` (divergencia ya declarada en `_RelationalMulti.write`): el
  comodelo no es un `BaseModel` y no tiene `browse` de ids nuevos.
- `_many2many_descriptor_set` (rama `NewId`) normaliza el valor con
  `_django_comodel_rows` antes de escribir: filas tal cual; ids → filas;
  comandos `SET`/`CLEAR`/`LINK`/`UNLINK`/`DELETE` aplicados sobre el valor
  en caché, como `write_new`.
- `_x2many_descriptor_get` devuelve el `QuerySet` en caché; si hay ids,
  los convierte en filas.

## Diferencia abierta, medida

`CREATE` y `UPDATE` hacia un comodelo de Django en un registro nuevo
levantan `ValueError`: la referencia crea `comodel.new(...)`
(`:1615-1621`) y un `QuerySet` no puede contener una fila sin guardar.
Población medida: **0** consumidores fuera de pruebas (la única
`Command.create` del árbol, `purchase_order.py:560`, escribe
`seller_ids` —inverso, no Many2many— sobre una plantilla guardada).
Condición de cierre: el primer consumidor; el sucesor es la unidad
`orm-many2many-django-comodel-create-0485` del plan.

## Pruebas

`tests/unit/orm/test_new_record_many2many_django_comodel.py` (8 casos).
Anulaciones: sin la lectura caen los 2 casos con valor; sin el
normalizador caen los 2 de comandos.
