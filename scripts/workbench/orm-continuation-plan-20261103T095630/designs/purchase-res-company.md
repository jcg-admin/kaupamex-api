# purchase: extensión de res.company

Unidad: `purchase-res-company-0397` (TASK-API-0397). Es la primera pieza
que necesita la máquina de estados de `purchase.order`
(`button_approve`, `_approval_allowed`).

## Contrato medido en la referencia

`odoo19c: addons/purchase/models/res_company.py` (`_inherit = 'res.company'`),
3 campos, 3 de 3 se portan:

| Campo | Línea | Forma aquí |
|---|---|---|
| `po_lock` | :10-14 | `Selection` `edit`/`lock`, default `edit` |
| `po_double_validation` | :16-20 | `Selection` `one_step`/`two_step`, default `one_step` |
| `po_double_validation_amount` | :22-23 | `Monetary`, default 5000 |

Mecanismo: el de `sale`. `extend_model('base', 'ResCompany', campos=…)`
desde `PurchaseConfig.ready()`, y las columnas en una migración de `base`
(precedente: `base/0064_rescompany_downpayment_account_and_more.py`).

## Casos (RED)

1. los tres campos existen en `res.company` con su default de la fuente;
2. sus valores de selección son los de la fuente;
3. una empresa nueva los recibe con esos defaults.

## Anulación

- retirar la llamada de `ready()`: caen los tres casos.

## Medición

- 3 de 3 en verde con la migración `base/0115` aplicada.
- Retirar la llamada de `PurchaseConfig.ready()`: caen exactamente los tres
  casos. La prueba se escribió antes que el código, pero no se ejecutó en
  rojo antes de implementar; esta anulación es su rojo.
- Incidente: la suite completa sobre `0c6b0b9f` corrió mientras este cambio
  se escribía en el árbol, y 13 casos que arrancan subprocesos leyeron un
  `ResCompany` con columnas que la base aún no tenía. Repetidos sobre un
  worktree limpio de `0c6b0b9f`, los 27 pasan; esa ejecución no vale como
  evidencia.
