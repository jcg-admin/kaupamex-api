# `copy` en todo modelo

Creado: 2026-11-13T05:45:56 (UTC). TASK-API-0485. Matriz: `designs/timestamped-copy-contract-matrix.md`.

## Contrato

`copy_data` (`odoo19c: odoo/orm/models.py:5406-5463`),
`copy_translations` (`:5465`) y `copy` (`:5530-5545`) cuelgan de
`BaseModel`: **todo** modelo los tiene.

## Estado medido (`fe9a477e`)

`copy` falta en 271 modelos concretos de `TimeStampedModel` y en 94 de
sólo Django; lo tienen los 63 de `BaseModel` y los 13 que declaran
`CopyMixin` a mano. `CopyMixin.copy` ya da de alta por
`DefaultGetMixin.create` o, si el modelo no lo adopta, por
`objects.create` (`src/orm/models.py:2192-2195`): sirve en cualquier
modelo concreto.

## Decisión

`adopt_copy` en `orm/model_classes.py`, con la forma de
`adopt_display_name`/`adopt_base_url`: instala los seis símbolos de
`CopyMixin` (`_copy_blacklist`, `copy_data`, `copy_children`,
`_copy_child_data`, `copy_translations`, `copy`) que el modelo no
resuelva ya por su MRO; `class_prepared` y barrido `ensure_copies` en
`base.apps.ready`. Excluye abstractos, proxies y terceros
(`THIRD_PARTY_MODULE_PREFIXES`). No se añade `CopyMixin` a las bases de
`TimeStampedModel`: los cuatro modelos que lo declaran delante romperían su
MRO.

Fuera de alcance, unidad propia `ir-exports-one2many-0485`:
`ir.exports.export_fields` como `One2many(copy=True)` (hoy sólo es un
`related_name`), que exige migración.

## Pruebas

- RED: `ir.exports` (`TimeStampedModel`) e `ir.exports.line` (sólo
  Django) no tienen `copy`.
- GREEN: el duplicado conserva los campos copiables, tiene otro `pk` y no
  copia las columnas mágicas.
- Censo: ningún modelo concreto propio sin `copy`.
- Anulación: sin el receptor ni el barrido caen las tres.
