# `account.payment`: la línea de método de pago y lo que cuelga de ella

Unidad: `account-payment-method-line-field-0515` (TASK-API-0515), paso 4 de
`designs/payment-method-line-chain.md`. Referencia: odoo-tools
`abe4040ec1`. Escrito el 2026-11-17, antes de tocar
`addons/account/models/account_payment.py`.

## Contrato de la referencia

| Símbolo | Cita | Contrato |
|---|---|---|
| `available_payment_method_line_ids` | `odoo19c: addons/account/models/account_payment.py:85-86` | Many2many calculado, no almacenado |
| `_compute_payment_method_line_fields` | `odoo19c: addons/account/models/account_payment.py:585-591` | las líneas disponibles del diario para el `payment_type`, menos los códigos de `_get_payment_method_codes_to_exclude` |
| `_get_payment_method_codes_to_exclude` | `odoo19c: addons/account/models/account_payment.py:610-613` | `ensure_one()`; `[]` |
| `payment_method_line_id` | `odoo19c: addons/account/models/account_payment.py:74-84` | Many2one calculado, almacenado, editable, `copy=False` |
| `_compute_payment_method_line_id` | `odoo19c: addons/account/models/account_payment.py:565-583` | la preferida del partner si está disponible; si no la actual si sigue disponible; si no la primera; si no vacío |
| `payment_method_id` | `odoo19c: addons/account/models/account_payment.py:87-92` | relacionado almacenado |
| `payment_method_code` | `odoo19c: addons/account/models/account_payment.py:176-177` | relacionado no almacenado |
| `outstanding_account_id` | `odoo19c: addons/account/models/account_payment.py:123-129` y `:620-623` | calculado almacenado: `payment_account_id` de la línea |
| `_check_payment_method_line_id` | `odoo19c: addons/account/models/account_payment.py:863-873` | obligatoria; si la línea tiene diario, es el del pago |
| `partner_id` | `odoo19c: addons/account/models/account_payment.py:116-122` | `res.partner`, `ondelete='restrict'` |
| `AccountPaymentMethodLine.unlink` | `odoo19c: addons/account/models/account_payment_method.py:150-162` | la línea usada por un pago pierde el diario y no se borra |

## Nuestro estado (medido en `32da44b9`)

- `AccountPayment` es `models.Model`, 10 campos, ningún método de pago
  (`grep payment_method addons/account/models/account_payment.py` → 0).
- `partner` apunta a `settings.AUTH_USER_MODEL` (`base.ResUsers`) con
  `SET_NULL`. La prosa heredada dice «Odoo partner_id → party».
  Clasificación: **FALSE** como porte: la fuente declara `res.partner` con
  `restrict`, y el cómputo de la línea lee
  `partner_id.property_inbound_payment_method_line_id`, que aquí vive en
  `ResPartner` (`addons/account/models/partner.py:267-296`). Lectores de
  `payment.partner` en addons: 0 (`grep -rn "\.partner\b"` sobre
  `account_check_printing` y `account_payment`).
- Sitios que crean un pago: 8 (corregido el 2026-11-17: el noveno acierto
  del `grep` era la declaración de la clase), en `tests/unit/account_check_printing`,
  `tests/unit/account_payment`, `tests/unit/account`,
  `tests/integration/account`.
- `account_check_printing` declara por escrito («Divergencia 1») que modela
  el cheque sin `payment_method_line_id` porque el pago no lo tenía. Con
  este campo esa nota pasa a **OUTDATED**; reconciliarla es su propia
  unidad, registrada aquí como sucesor, no parte de este cambio.

## Pasos (cada uno con su prueba y su anulación)

1. **Adopción**: `class AccountPayment(models.BaseModel, TimeStampedModel)`.
   Los ocho sitios de creación pasan a ejecutarse con entorno (`sudo`).
2. **`partner`**: `res.partner`, `PROTECT`. Migración con paso de datos: el
   usuario se sustituye por su `partner`.
3. **Campos y cómputos** de la tabla, con los nombres de la fuente
   (`payment_method_line_id` como columna `payment_method_line_id`,
   `SET_NULL`, el default de un Many2one no requerido).
   Migración `0044` de `account` con `ComputeStoredFields` para
   `payment_method_line_id`, `payment_method_id`, `outstanding_account_id`.
4. **`_check_payment_method_line_id`**.
5. **`AccountPaymentMethodLine.unlink`** y, con él, `AccountJournal.unlink`
   deja de borrar líneas usadas.

## Pruebas

`tests/unit/account/test_payment_method_line_field.py`:

| Caso | Espera |
|---|---|
| pago entrante en diario de banco | `payment_method_line_id` es la línea manual entrante; `payment_method_code == 'manual'` |
| partner con preferida disponible | gana la preferida |
| partner con preferida de otro diario | se ignora; primera disponible |
| diario sin líneas | `ValidationError` de `_check_payment_method_line_id` |
| línea de otro diario escrita a mano | `ValidationError` |
| `outstanding_account_id` | sigue a `payment_account_id` de la línea |
| `unlink` de línea usada | la fila sigue, `journal_id` nulo |
| `unlink` de línea sin uso | la fila desaparece |
| borrar un `res.partner` con pagos | rehúsa |

Anulaciones: retirar la rama de la preferida; retirar la segunda rama de la
restricción; retirar el filtro de uso en `unlink`. Cada una tumba sólo sus
casos.

*Métrica:* valores leídos de la base tras `flush_all`.
*Ciega a:* los lectores de la línea fuera de esta cadena (`:248-250`,
`:271`, `:326`, `:433`, `:649-655`, `:977`, `:1138`), que entran con el
porte de cada método que los contiene.
