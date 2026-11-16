# `copy_data` de `account.move.line` y sus campos de negocio — diseño

Unidad: `account-copy-data-business-fields-0397` (citada a `TASK-API-0121`).

## Fuente

| Símbolo | Dónde | Qué hace |
|---|---|---|
| `AccountMoveLine.copy_data` | `account/models/account_move_line.py:2071-2086` | sobre la copia genérica: no copia el `name` de una línea de plazo de pago de factura; quita `balance` y `account_id` de secciones y notas; quita `balance` de una línea de producto de factura (se recalcula del precio); con `include_business_fields` en el contexto llama a `_copy_data_extend_business_fields` |
| `AccountMoveLine._copy_data_extend_business_fields` | `:3765-3766` | base vacía (`ensure_one`) |
| override de `purchase` | `purchase/models/account_invoice.py:532-535` | añade `purchase_line_id` |
| override de `sale` | `sale/models/account_move_line.py:36-39` | añade `sale_line_ids` como `[(6, None, ids)]` |

Consumidores en la fuente: `AccountMove._reverse_moves` (`account_move.py:5476-5480`,
`copy` con `include_business_fields=True`) y el asistente de reversión
(`wizard/account_move_reversal.py:144`).

## Estado del puerto (medido 2026-11-16)

- `AccountMoveLine` hereda la `copy_data` genérica (`orm/models.py`,
  `CopyMixin`), que devuelve un dict por instancia; no tiene el override.
- `include_business_fields`: 0 apariciones fuera de pruebas.
- `account/wizard/account_move_reversal.py` recrea los asientos campo a campo
  y su cabecera dice que `copy_data` «no existe en este árbol». Es falso
  desde que `CopyMixin` lo porta.

## Esta unidad

1. `copy_data` de la línea, con las tres exclusiones y el gancho, sobre la
   genérica (`wrap_method` no aplica: el modelo es de `account`, se define en
   su clase).
2. La base de `_copy_data_extend_business_fields` en `account` y sus dos
   overrides, encadenados con `wrap_method` desde `purchase` y `sale`.
3. Corregir la afirmación caducada de la cabecera del asistente.

## Sucesor

`account-reverse-moves-copy-0121`: llevar `_reverse_moves` y el asistente a
`copy()` con `include_business_fields`, como la fuente, en lugar de la
recreación campo a campo.

## Pruebas (RED)

- la copia de una línea de producto de factura no lleva `balance`;
- la de una sección no lleva `balance` ni `account_id`;
- la de una línea de plazo de pago de factura no lleva `name`;
- sin el contexto, la copia no lleva `purchase_line_id` ni `sale_line_ids`;
- con `include_business_fields`, lleva `purchase_line_id` y
  `sale_line_ids == [(6, None, ids)]`.

Anulación: retirar el gancho de `copy_data` hace caer exactamente las dos de
`include_business_fields`.

## Medido al implementar (2026-11-16)

- La copia genérica llega a `AccountMoveLine` por adopción, no por la MRO
  (`issubclass(AccountMoveLine, CopyMixin)` es falso), así que el `super()`
  de la fuente se escribe `CopyMixin.copy_data(self, …)`.
- Copiar un asiento **no** copia hoy sus líneas, por dos piezas que pertenecen
  al sucesor `account-reverse-moves-copy-0121` y no a esta unidad:
  1. `line_ids` es el inverso del FK `move` y no un `One2many(copy=True)`
     como en la fuente (`account_move.py`, `line_ids`); `copy_children` sólo
     copia `One2many` declarados con `copy=True`;
  2. `CopyMixin._copy_child_data` llama al `copy_data` del hijo sólo si el hijo
     hereda de `CopyMixin`; un modelo que lo adopta (como la línea) se copia
     con la función del mixin y se salta su override. La fuente llama siempre
     al del modelo.
  Medido con una prueba que copiaba un asiento: `ValueError: not enough
  values to unpack (expected 1, got 0)`, ninguna línea copiada.
- `sale` lleva la cabecera `_inherit = 'account.move.line'` como constante de
  módulo en el archivo con el nombre de su fuente, y la fila en
  `EXTENSION_ONLY_CLASSES` del guardián de cabeceras de `sale`.

Anulación: sin el gancho de `include_business_fields` caen exactamente las dos
pruebas que dependen de él (de 7).

## Episodio: el decorador robado (2026-11-16)

La primera versión insertó `copy_data` sustituyendo el texto
`    def _compute_balance(self):` por los métodos nuevos seguidos de esa línea.
`_compute_balance` lleva `@api.depends('debit', 'credit')` justo encima, así
que el decorador pasó a decorar `copy_data` y `balance` dejó de recalcularse al
tocar `debit` (`test_compute_wiring.py::TestTheCycleReachesTheColumn`, rojo en
el subconjunto derivado, verde en HEAD). Una bisección por archivo en un
worktree aislado acotó la causa a `account_move_line.py`; las dos primeras
bisecciones dentro del archivo no la vieron porque dejaban el decorador
fuera de lugar. Corregido moviendo los métodos nuevos encima del decorador.
La inserción equivalente de `purchase-product-0397`
(`_compute_product_uom_qty` antes de `_compute_selected_seller_id`) se revisó:
ese método no lleva decorador.
