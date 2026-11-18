# Bloque C: los parciales de conciliación y el borrado de apuntes

Unidad: `orm-fk-delete-policy-contract-0515` (TASK-API-0515), las dos
últimas filas del contrato: `account.AccountPartialReconcile.debit_move` y
`credit_move`. Escrito el 2026-11-18 durante la F2 de `02cec092`, antes de
tocar ningún modelo de `account` de este bloque.

## Contrato de la referencia (verificado por el coordinador)

| Símbolo | Cita | Contrato |
|---|---|---|
| `debit_move_id`, `credit_move_id` | `odoo19c: addons/account/models/account_partial_reconcile.py:15-20` | obligatorios, sin `ondelete`: `restrict` |
| `account.move.line.move_id` | `odoo19c: addons/account/models/account_move_line.py:32-41` | `ondelete="cascade"` |
| `remove_move_reconcile` | `odoo19c: addons/account/models/account_move_line.py:3138-3140` | `(self.matched_debit_ids + self.matched_credit_ids).unlink()` |
| `account.move.line.unlink` | `odoo19c: addons/account/models/account_move_line.py:1984-1988` | `if not self: return True`; `self.remove_move_reconcile()`; después bloqueos fiscales, registro y `super().unlink()` |
| `account.move.unlink` | `odoo19c: addons/account/models/account_move.py:4055-4064` | `self.line_ids.remove_move_reconcile()`, `self.line_ids.unlink()`, `super().unlink()` |
| `account.partial.reconcile.unlink` | `odoo19c: addons/account/models/account_partial_reconcile.py:105-147` | guarda el `full_reconcile_id` y los apuntes; `super().unlink()`; borra el full; revierte o borra los asientos de caja base y de diferencia de cambio; recalcula `matching_number`; repone los pagos |

La base rehúsa borrar un apunte con parciales; el apunte y el asiento se
pueden borrar porque su `unlink` quita antes la conciliación.

## Nuestro estado (medido en `02cec092`)

- `AccountMove(SequenceMixin, models.Model)`,
  `AccountMoveLine(AnalyticMixin, models.Model)`,
  `AccountPartialReconcile(models.Model)` y
  `AccountFullReconcile(models.Model)`: ninguno adopta `BaseModel`, ninguno
  declara `unlink` ni `remove_move_reconcile`.
- `AccountPartialReconcile.delete_and_update_matching`
  (`addons/account/models/account_partial_reconcile.py:156`) es el `unlink`
  simplificado; su cabecera declara tres divergencias (sin caja base, sin
  `exchange_move_id`, sin reapertura de pagos).
- Los dos campos son `CASCADE`: borrar un apunte borra sus parciales sin
  recalcular nada.
- Consumidores: 37 archivos de `tests` y 106 de `addons`/`src` nombran
  `AccountMove` o `AccountMoveLine`
  (`grep -rlE "AccountMove\b|AccountMoveLine\b"`).

## Riesgo y orden

Adoptar `BaseModel` en `account.move` y `account.move.line` es el cambio
más ancho de la sesión. Se hace en pasos que se verifican por separado:

1. **C1 — `AccountPartialReconcile` y `AccountFullReconcile` adoptan
   `BaseModel`**; `unlink` de cada uno con el orden de la fuente
   (`odoo19c: addons/account/models/account_partial_reconcile.py:105` y
   `odoo19c: addons/account/models/account_full_reconcile.py:47`).
   `delete_and_update_matching` se retira en los dos modelos: no existe en
   la fuente y sus dos únicos llamadores eran
   `tests/unit/account/test_account_reconcile.py`, que pasan a `unlink`.
   Corrección medida contra la fuente: `AccountPartialReconcile.unlink`
   borra la conciliación total siempre (`full_to_unlink.unlink()`), no
   sólo cuando queda sin parciales, como hacía el método retirado. Las
   tres divergencias declaradas siguen declaradas en el archivo.
2. **C2 — `AccountMoveLine` adopta `BaseModel`**: `remove_move_reconcile` y
   `unlink` (los dos primeros pasos de la fuente y `super().unlink()`; los
   bloqueos fiscales y el registro quedan `pendiente:` con su cita).
3. **C3 — `AccountMove` adopta `BaseModel`**: `unlink` con
   `remove_move_reconcile` y el borrado de líneas.
4. **C4 — la política**: `debit_move` y `credit_move` a `PROTECT`;
   migración `0046_restrict_partial_reconcile_moves` de `account`.

Si C2 o C3 rompen más de lo que su diseño puede absorber, se detiene ahí,
se registra la medición y C4 no se aplica: la política sin los `unlink`
convertiría en error el borrado de un asiento conciliado, que la fuente
permite.

## Pruebas

`tests/unit/account/test_reconcile_delete_contract.py`:

| Caso | Espera |
|---|---|
| borrar la fila de un apunte con un parcial, sin `unlink` | `ProtectedError`; el parcial sigue |
| `line.unlink()` con un parcial | el parcial desaparece y el `matching_number` del otro apunte se recalcula |
| `move.unlink()` con líneas conciliadas | asiento, líneas y parciales desaparecen |
| `partial.unlink()` del único parcial de una conciliación total | el full desaparece |
| `partial.unlink()` de uno de dos parciales de una conciliación total | el full desaparece; los apuntes del parcial que queda toman `P<n>` |
| `full.unlink()` | el parcial sigue y los apuntes vuelven a `P<n>` |
| `unlink()` de un conjunto vacío de parciales | `True`, sin consultas de borrado |

Más las dos filas del contrato. Anulaciones: sin `remove_move_reconcile` en
`AccountMoveLine.unlink` cae el segundo; sin él en `AccountMove.unlink` cae
el tercero; con `CASCADE` caen el primero y las dos filas.

*Métrica:* filas de parciales, fulls, apuntes y asientos leídas de la base.
*Ciega a:* caja base, diferencia de cambio y pagos, que el parcial no
modela todavía.
