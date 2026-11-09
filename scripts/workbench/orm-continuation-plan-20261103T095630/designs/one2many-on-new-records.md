# El One2many declarado sobre registros de `new()`

Referencia: `odoo-tools@abe4040ec1a45beee90fb694e4eae4453e46b389`, Odoo 19 Community.

## Contrato de la referencia

- Un registro de `new()` vive sólo en la caché: leer su One2many devuelve el
  valor en caché (vacío si nadie lo puso), sin consulta.
- `BaseModel._update_cache` ajusta el inverso de los registros **nuevos** del
  comodelo con `invf._update_inverse(inv_recs, self)`; para un One2many es
  `_RelationalMulti._update_inverse` (`odoo/orm/fields_relational.py:564-573`):
  suma el id nuevo al valor en caché, o lo deja como parche si aún no hay
  valor.
- `Many2one.write` (`:400-424`) hace `_remove_inverses` del corregistro
  anterior y `_update_inverses` del nuevo: añade el registro al valor en caché
  del One2many del corregistro si hay valor en caché o si el corregistro es
  nuevo (`ids0 is not None or not corecord.id`).

## Medido (sonda sobre `test_orm.discussion.messages`, One2many declarado)

- `D.new({...}).messages` → `TypeError: Field 'id' expected a number but got
  <NewId>`: `One2many.__get__` (`src/orm/fields_relational.py:508-531`) cae al
  `filter` de Django con el `NewId`. El descriptor inverso de Django
  (`_x2many_descriptor_get`, `models.py:5282`) ya lee la caché
  `field_data[rel]` para un `NewId`; el campo declarado no.
- `field_inverses[message.discussion]` devuelve los tres `One2many`
  declarados de `discussion`, y ninguno tiene `_update_inverse`: el ajuste de
  `_update_cache` no tiene receptor en el campo declarado.

## Diseño (por pasos, una unidad cada uno)

1. **Lectura:** `One2many.__get__` con un dueño de `new()` lee
   `field_data[inverse.remote_field]` — la misma clave que escriben
   `_write_new_one2many` y lee el descriptor inverso.
2. **`_update_inverse`:** el campo declarado delega en
   `_relational_multi_update_inverse` sobre la relación inversa, con la misma
   clave de caché.
3. **`Many2one.write`:** `_remove_inverses`/`_update_inverses` sobre la
   caché de los corregistros nuevos (los reales se leen de la base aquí, así
   que no tienen caché que ajustar: divergencia de mecanismo declarada).

## Paso 3, concreto

- La asignación de un registro nuevo pasa por `FieldDescriptor.__set__`
  (`src/orm/fields.py:1912-1915`), que escribe la caché del `NewId` **antes**
  de `field.write`; ahí se pierde el corregistro anterior. El ajuste va
  alrededor de esa escritura: `_remove_inverses` antes, `_update_inverses`
  después, para un `ForeignKey`.
- La caché de las líneas es `field_data[self.remote_field]`, la misma de los
  pasos 1 y 2.
- **Divergencia declarada:** los One2many declarados sobre el mismo Many2one
  comparten esa clave, así que el `domain` de cada uno
  (`invf.get_comodel_domain`, `:453`) no se aplica a las líneas de un dueño
  nuevo. La referencia guarda una caché por campo.
