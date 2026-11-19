# `account_edi` sobre `BaseModel`, con su ACL

Unidad hija `basemodel-adoption-account-edi-0397` del paraguas
`basemodel-adoption-0397` (TASK-API-0397), con la forma de
`basemodel-adoption-authz-totp.md`.

## Contrato medido en la referencia

- `account.edi.format` (`odoo19c: addons/account_edi/models/account_edi_format.py`)
  y `account.edi.document`
  (`odoo19c: addons/account_edi/models/account_edi_document.py`).
- `odoo19c: addons/account_edi/security/ir.model.access.csv`: 4 filas, lectura
  para `base.group_user` y CRUD para `account.group_account_invoice` en cada
  modelo. Es el único archivo de seguridad del manifiesto
  (`odoo19c: addons/account_edi/__manifest__.py:17`).
- `_compute_edi_format_ids`
  (`odoo19c: addons/account_edi/models/account_journal.py:54-79`) lee y
  asigna `edi_format_ids` como recordset.

## Accesores, medidos

| Accesor | Lado | Con la adopción |
|---|---|---|
| `move.edi_document_ids` | `account.move` (aún Django) → documento | `RelatedManager`: conserva `.all()` |
| `journal.edi_format_ids` | `account.journal` (`BaseModel`) → formato | recordset: sin `.filter`/`.set`/`.all` |
| `edi_format.journals` | formato → diario | recordset |

Consumidores del segundo, que pasan al API de recordset:
`compute_edi_format_ids` (`addons/account_edi/models/account_journal.py`), con
`ids`, `filtered` y `write` con `fields.Command.set`, y
`_create_edi_documents_after_post` de `account_move.py`, que recorre
`journal.edi_format_ids` (≙ `odoo19c: addons/account_edi/models/account_move.py:240`). `write` con comandos pasa por el manager de Django, que
emite `m2m_changed`: `_guard_edi_format_removal` sigue disparando.

## Cambios

1. `AccountEdiFormat` y `AccountEdiDocument` derivan de `models.BaseModel`
   (que ya trae `RecordLoaderMixin`).
2. `addons/account_edi/security/ir.model.access.csv`, copia fiel, en `data`
   del manifiesto.
3. Los consumidores de la tabla de arriba.
4. `test_basemodel_reach.py`: `account_edi` sale de `PENDING`.

## Pruebas

`tests/unit/account_edi/test_account_edi_basemodel.py`: los dos modelos son
`BaseModel`; las 4 filas del CSV; un usuario interno lee y no escribe un
documento; `compute_edi_format_ids` activa el formato por defecto y conserva
el ya activo. Las dos últimas caen sin el cambio de consumidores
(`'AccountEdiFormat' object has no attribute 'filter'`).

## Lo que esta unidad no cierra

- `_guard_edi_format_removal` no tiene prueba: exige asientos con documentos
  en `to_send`, y `account.move` sigue fuera de `BaseModel`. Queda con la
  adopción de `account` (`account` sigue en `PENDING`).
