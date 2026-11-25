# `account.account.write`: las tres ramas previas (`account-account-write-branches-0397`)

Sucesor declarado en `designs/account-account-mc2c.md`. TASK-API-0397.

## Lo que dice la referencia

`odoo19c: addons/account/models/account_account.py:1053-1077`. Antes de
escribir, `write` recorre tres ramas:

1. `reconcile` (`:1054-1058`): al activarlo, `_toggle_reconcile_to_true`
   sobre las cuentas que no lo tenían (`:955-971`); al desactivarlo,
   `_toggle_reconcile_to_false` sobre las que sí (`:973-997`).
2. `currency_id` (`:1060-1063`): si alguna línea de la cuenta tiene otra
   divisa extranjera (`currency_id not in (False, nueva)`), `UserError`
   *"You cannot set a currency on this account as it already has some
   journal entries having a different foreign currency."*
3. `deprecated` (`:1065-1066`): si alguna línea de reparto de impuestos usa
   la cuenta, `UserError` *"You cannot deprecate an account that is used in
   a tax distribution."*

Tras escribir (`:1070-1075`), con `defer_account_code_checks` ausente del
contexto y `company_ids`/`code` en los valores, invalida `company_ids` si se
escribió y llama a `_ensure_code_is_unique`.

## Lo que hay en el puerto (medido)

- `AccountAccount.write` sólo tiene la rama de unicidad (MC2c-1).
- `account.move.line` tiene `account`, `currency`, `debit`, `credit`,
  `full_reconcile` y los inversos `matched_debit_ids`/`matched_credit_ids`
  (`account_partial_reconcile.py`). **No** tiene `amount_residual`,
  `amount_residual_currency`, `reconciled` ni `amount_currency`: su
  docstring los declara diferidos porque dependen de `amount_currency`
  multimoneda.
- `account.tax.repartition.line` tiene `account`.

## La unidad

- `write`: las ramas 2 y 3 tal cual, la rama 1 a través de los dos métodos,
  y la guarda `defer_account_code_checks` con la invalidación de
  `company_ids` antes de `_ensure_code_is_unique`.
- `_toggle_reconcile_to_false`: la comprobación de conciliaciones parciales
  pendientes (`:980-989`), con su `UserError` verbatim *"You cannot switch an
  account to prevent the reconciliation if some partial reconciliations are
  still pending."*
- **Bloqueo medido, con sucesor:** el `UPDATE` de `_toggle_reconcile_to_true`
  (`:962-971`) y el de `_toggle_reconcile_to_false` (`:991-997`) escriben
  `reconciled`, `amount_residual` y `amount_residual_currency`, columnas que
  `account.move.line` no tiene. Los dos métodos se declaran con el `UPDATE`
  pendiente; sucesor `account-move-line-residual-0397` (portar esas columnas
  y `amount_currency`).

Símbolos tocados: `AccountAccount.write`,
`AccountAccount._toggle_reconcile_to_true`,
`AccountAccount._toggle_reconcile_to_false`.

## Tests

`tests/unit/account/test_account_account_write_branches.py`:

- moneda nueva con un apunte en otra divisa → `UserError`; apunte sin divisa
  o en la misma → pasa;
- deprecar una cuenta usada en una línea de reparto → `UserError`; sin uso →
  pasa;
- desactivar `reconcile` con una conciliación parcial pendiente →
  `UserError`; sin parciales → pasa.

Anulación: retirada cada rama, cae exactamente su caso negativo.
