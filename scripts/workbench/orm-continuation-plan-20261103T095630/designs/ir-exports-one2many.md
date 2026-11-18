# `ir.exports.export_fields` como `One2many(copy=True)`

Creado: 2026-11-18T11:51:29 (UTC). TASK-API-0485, ítem del plan
`ir-exports-one2many-0485`. Referencia: odoo-tools `abe4040ec1`, Odoo 19
Community. Viene de `copy-universality.md`, que lo dejó fuera de alcance.

## El contrato de la fuente

`odoo19c: odoo/addons/base/models/ir_exports.py:7-23`, medido con
`scripts/census_class.py --prefix _`:

| Clase | Atributos de clase | Campos |
|---|---|---|
| `IrExports` | `_name='ir.exports'`, `_description='Exports'`, `_order='name, id'` (`:8-10`) | `name`, `resource` (`index=True`), `export_fields = One2many('ir.exports.line', 'export_id', string='Export ID', copy=True)` (`:14`) |
| `IrExportsLine` | `_name='ir.exports.line'`, `_description='Exports Line'`, `_order='id'` (`:18-20`) | `name`, `export_id = Many2one('ir.exports', string='Export', index=True, ondelete='cascade')` (`:23`) |

Consecuencia que el defecto rompe: `copy()` de una exportación duplica sus
líneas, porque `export_fields` declara `copy=True`.

## Este árbol, medido

- `IrExports`: sin atributos de clase; `export_fields` sólo existe como
  `related_name` de la FK del hijo, y un reverso no declarado no se copia
  (`CopyMixin.copy_children`, H-API-1161). Duplicar una exportación deja
  las líneas atrás.
- `IrExportsLine`: sin atributos de clase; la FK se llama `export` (forma A),
  columna `export_id`.
- Consumidores: `addons/web/controllers/export.py:730`
  (`export.export_fields.order_by('id')`) y
  `tests/unit/orm/test_copy_universality.py:33-36` (`export=`, `export_id`).

## Decisión

Precedente: la migración `0099_declared_one2many_copied_children` hizo lo
mismo con `ir.actions.server.child_ids`.

1. `IrExports` declara los tres atributos de clase y
   `export_fields = fields.One2many('ir.exports.line', 'export_id',
   string='Export ID', copy=True)`. `fields.One2many` reusa el manager del
   reverso, así que `export.export_fields.order_by('id')` sigue igual.
2. `IrExportsLine` declara sus tres atributos de clase y la FK pasa a la
   forma C: `export_id = fields.Many2one(IrExports, ...,
   related_name='+', db_column='export_id')`. La columna se conserva.
3. Migración: `RenameField` `export` → `export_id` y `AlterField` con
   `db_column='export_id'` y `related_name='+'`. Ninguna columna cambia.
4. Consumidor: `test_copy_universality.py` pasa a `export_id=` y lee
   `export_id_id`.

## RED (`tests/unit/base/test_ir_exports.py`, el `verify` del plan)

1. los atributos de clase de las dos clases son los de la fuente;
2. `copy()` de una exportación con dos líneas da una exportación nueva con
   dos líneas nuevas, con los mismos nombres y en el mismo orden;
3. las líneas originales siguen colgando de la original.

Anulación: con `copy=False` en `export_fields` cae exactamente el caso 2.
