# Restricciones Python de los campos almacenados en `create` y `write`

Fecha: 2026-11-10T04:57:58 (`date -u`). Referencia: odoo-tools
`abe4040ec1`, `odoo19c: odoo/orm/models.py`.

## Contrato de la referencia

| Punto | Línea | Qué valida |
|---|---|---|
| `_create` | `:4948-4949` | `records._validate_fields(name for data in data_list for name in data['stored'])`, después de `modified` y de `other_fields`, antes de `check_access('create')` |
| `create` | `:4741` | los inversos no almacenados, excluyendo los almacenados (ya portado, `models.py:1017`) |
| `write` | `:4490-4491` | `real_recs._validate_fields(vals, inverse_fields)` tras escribir y `modified(vals)` |
| `write` | `:4514` | `real_recs._validate_fields(inverse_fields)` tras los inversos |
| `_compute_field_value` | `:4954-4959` | los calculados almacenados (ya portado, H-API-1165) |

`_validate_fields` (`:1253-1268`) compara **nombres de campo**: allá cada
campo tiene un solo nombre.

## Estado medido en este árbol

- `_create` (`DefaultGetMixin`, `models.py:1118`) termina tras `modified` sin
  validar: **ninguna** `@api.constrains` sobre un campo almacenado corre al
  crear.
- `RecordLoaderMixin.write` (`:2877`) y `BaseModel.write` (`:9843`) tampoco
  validan.
- Medido: 52 archivos y 96 decoradores `@api.constrains` bajo `addons/` y
  `src/` (`grep -rn "@api.constrains\|@constrains("`). Hoy sólo corren tras un
  recómputo o por un inverso no almacenado.
- Un `Many2one` tiene **dos** nombres en `model_field_registry`: `skill` y
  `skill_id` resuelven al mismo objeto campo. Los `vals` llegan con el nombre
  Django (`skill`) y las restricciones portadas declaran el de la fuente
  (`skill_id`); la comparación literal de `_validate_fields` las separa.

Destapado por la unidad U3 de `hr-individual-skill-mixin-full-port.md`: sus
pruebas de solapamiento no levantaban aunque el método estaba registrado.

## Diseño

1. `_validate_fields` compara por **campo**: cada nombre, de los dos lados
   (tocados, excluidos y declarados), se lleva a `field.name` con
   `model_field_registry`; un nombre que no es campo se conserva tal cual.
   Misma semántica que la fuente, donde el nombre es único.
2. `_create`: tras el bloque de `protecting`/`modified`, validar los campos
   almacenados de todo el lote. Un `BaseModel` recibe el recordset
   (`cls._from_ids`), así que una restricción de lote —como
   `_check_not_overlapping_regular_skill`— ve el lote entero; un modelo de
   Django valida fila a fila con `Model._validate_fields`.
3. `write`: `RecordLoaderMixin.write` valida `values` tras guardar la fila
   cuando el receptor no es un `BaseModel`; `BaseModel.write` valida una vez
   sobre `self` tras escribir todos los registros. `check_access('create')`
   tras la validación queda fuera: `create` ya lo comprueba antes.

## Riesgo y verificación

Activar 96 restricciones dormidas puede destapar datos de prueba que las
violan. Es un cambio transversal del ORM: suite completa y `ci-multidb`.

Controles de anulación: retirar la llamada de `_create` debe tumbar las
pruebas de creación de U3; retirar la de `write`, sus pruebas de escritura;
retirar la normalización por campo, las que declaran `skill_id`.
