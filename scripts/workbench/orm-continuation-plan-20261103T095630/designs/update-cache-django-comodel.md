# `_update_cache` con un comodelo de Django sin `BaseModel`

Referencia: `odoo-tools@abe4040ec1a45beee90fb694e4eae4453e46b389`, Odoo 19 Community.

## Contrato de la referencia

`BaseModel._update_cache` (`odoo/orm/models.py`, el bloque *"set inverse
fields on new records in the comodel"*): tras poner cada valor relacional en
caché toma `self[field.name].filtered(lambda r: not r.id)` y, si hay
registros **nuevos** del comodelo, les ajusta el inverso con
`_update_inverse`. Un valor vacío o de registros reales no hace nada.

## Medido (sonda y RED)

- `test_orm.message.new({'author': uid})` (Many2one a `res.users`, modelo
  de Django sin `BaseModel`): `AttributeError: 'ResUsers' object has no
  attribute 'filtered'`.
- `new({'author': False})`: `AttributeError: 'NoneType' object has no
  attribute 'filtered'`.
- `src/orm/models.py:7105` porta la línea verbatim; un comodelo de Django
  devuelve una fila o `None`, no un recordset.

## Diseño

Si el valor no es un recordset (no tiene `filtered`), es una fila de Django,
que ya existe, o `None`: no hay registro nuevo cuyo inverso ajustar, y el
bucle sigue. Es el mismo veredicto que la referencia da a un valor vacío o de
registros reales.

## Segunda divergencia, registrada para la unidad siguiente

`Many2one.write` llama `_remove_inverses`/`_update_inverses`
(`odoo/orm/fields_relational.py:400-424`): asignar `new.discussion = d1` con
`d1.messages` en caché añade el `NewId` a esa caché. Aquí `d1.messages` sigue
`[]` (sonda ejecutada en Kaupamex; la expectativa de la referencia es
inferencia estática del código).
