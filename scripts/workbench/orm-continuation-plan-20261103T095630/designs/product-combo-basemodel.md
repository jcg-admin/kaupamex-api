# product.combo y product.combo.item a BaseModel

Unidad `basemodel-adoption-0397`, tramo product. Referencia
`odoo19c: addons/product/models/product_combo.py` (79 líneas) y
`odoo19c: addons/product/models/product_combo_item.py` (33 líneas).

## Estado heredado medido

Los dos modelos son Django con `TimeStampedModel`. Las invariantes viven en
`clean()` y en `ProductCombo.check_has_items()`, que alguien tiene que llamar:
la prosa del módulo lo justifica con que Django persiste el padre antes que
los hijos. Con `BaseModel.create`, el One2many llega como comandos en la
misma escritura y la restricción corre después de escribirlos, igual que en
la fuente. La justificación ya no es cierta.

Dos frases de prosa heredada son falsas:

| Prosa | Medido | Veredicto |
|---|---|---|
| `ResCurrency._convert` no está portado | `src/addons/base/models/res_currency.py:536` | falso |
| `_get_main_company()` no existe | `ResCompany.get_main_company` (`src/addons/base/models/res_company.py:926`) | falso; el nombre diverge |

## Contrato a portar

`ProductCombo`:
- `ProductCombo._compute_combo_item_count` (`:33-43`)
- `ProductCombo._compute_currency_id` (`:45-51`), con respaldo a la compañía
  principal
- `ProductCombo._compute_base_price` (`:53-63`), con `_convert`
- `ProductCombo._check_combo_item_ids_not_empty` (`:65-68`)
- `ProductCombo._check_combo_item_ids_no_duplicates` (`:70-74`)
- `ProductCombo._check_company_id` (`:76-80`)
- `sequence` lleva `copy=False` y `combo_item_ids` lleva `copy=True`.

`ProductComboItem`:
- `company_id` related a `combo_id.company_id`, almacenado y precalculado
- `currency_id` y `lst_price` related al producto
- `ProductComboItem._check_product_id_no_combo` (`:30-33`)
- el `domain` del producto

Las citas se pasan a la línea `def` antes de commitear.

## Por decidir al implementar

- `ResCompany` no es BaseModel y su moneda se llama `currency`, no
  `currency_id`. Hay que medir qué expone el related.
- El M2M `combo_ids` la referencia lo declara en `product.template`; aquí se
  declara del lado del combo (`product_tmpls`). Moverlo es su propia unidad.
- `check_has_items` y `check_combo_choices` del template tienen
  consumidores; se buscan antes de retirarlos.
