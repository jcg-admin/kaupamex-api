# Cadena `payment_method_line_id`: diario → pago → `unlink` de la línea

Unidad padre: `account-payment-method-line-field-0515` (TASK-API-0515).
Referencia: odoo-tools `abe4040ec1`, alias `odoo19c:`. Estudio escrito el
2026-11-17 durante la F2 de `ed74f56d`, **antes** de tocar código de esta
cadena (secuencia: este commit precede a los de implementación).

## 1. Flujo de la referencia (quién escribe, quién lee)

| Paso | Símbolo | Cita | Efecto |
|---|---|---|---|
| 1 | `account.payment.method.create` | `odoo19c: addons/account/models/account_payment_method.py:20-38` | por cada método `mode == 'multi'`, crea una línea en cada diario que cumple `_get_payment_method_domain` |
| 2 | `_get_payment_method_domain` | `:40-61` | `type in ('bank','cash','credit')`, más moneda y país si la información los declara |
| 3 | `account.journal.inbound/outbound_payment_method_line_ids` | `odoo19c: addons/account/models/account_journal.py:205-233` | One2many **calculado almacenado** sobre `journal_id`, dominio por `payment_type` |
| 4 | `_compute_inbound/outbound_payment_method_line_ids` | `:462-504` | depende de `type`, `currency_id`; `Command.clear()` y una línea por método por defecto (`account.account_payment_method_manual_in/out`, `:59-63`) en diarios bank/cash/credit |
| 5 | `_get_available_payment_method_lines(payment_type)` | `:1188-1203` | devuelve las inbound u outbound del diario; vacío si no hay diario |
| 6 | `account.payment.available_payment_method_line_ids` | `odoo19c: addons/account/models/account_payment.py:85-86`, cómputo `:585-591` | líneas disponibles del diario para el `payment_type`, menos los códigos excluidos |
| 7 | `account.payment.payment_method_line_id` | `:74-84`, cómputo `:565-583` | preferida del partner (`property_*_payment_method_line_id`) si está disponible; si no, la actual si sigue disponible; si no, la primera disponible; si no, `False` |
| 8 | `payment_method_id`, `payment_method_code` | `:87-92`, `:176-177` | relacionados almacenados / no almacenados |
| 9 | `_check_payment_method_line_id` | `:863-873` | obligatorio; la línea debe pertenecer al diario del pago |
| 10 | `outstanding_account_id` | `:620-623` | sale de `payment_account_id` de la línea |
| 11 | `AccountPaymentMethodLine.unlink` | `odoo19c: addons/account/models/account_payment_method.py:150-162` | línea usada por un pago: se le quita el diario y no se borra |

Lectores adicionales de la línea en el pago: `:248-250` (cuentas de
pendientes), `:271`, `:326`, `:433`, `:649-655`, `:977`, `:1138`. Quedan
fuera de esta cadena y se cubren con el porte de cada método que los contiene.

## 2. Binario (Django 6.0.5 + este ORM)

Un One2many calculado almacenado existe en este ORM (`One2many` sobre
registros nuevos y `Command`, unidades 42-45 de la sesión). La línea declara
hoy `payment_type`, `code`, `company`, `default_account` como `property` de
Python, no como campos relacionados: un dominio `('payment_type','=',…)`
sobre ellas no se traduce a SQL.

## 3. Nuestro estado (`ed74f56d`)

| Pieza | Hoy |
|---|---|
| `AccountJournal` | `models.Model` (254 líneas contra 1307); sin `inbound/outbound_payment_method_line_ids` ni `_get_available_payment_method_lines` |
| datos `account_payment_method_manual_in/out` | no existen (`grep` → 0) |
| `AccountPaymentMethod.create` / `_auto_link_payment_methods` / `_get_payment_method_domain` | no existen |
| línea: `payment_type`, `code`, `company`, `default_account` | `property`, no campos |
| `AccountPayment` | 10 de 46 campos; sin `payment_method_line_id`, `available_payment_method_line_ids`, `payment_method_id`, `payment_method_code`, `outstanding_account_id` |

## 4. Unidades (orden por dependencia)

1. `account-payment-method-line-related-0515` — `payment_type`, `code`,
   `company_id`, `default_account_id` de la línea como campos relacionados
   (`:126-129`, `:122-124`). Precondición del dominio del paso 3.
2. `account-payment-method-defaults-0515` — registros de datos
   `account_payment_method_manual_in/out` (`odoo19c: addons/account/data/
   account_data.xml:129-138`), `_get_payment_method_domain`, `create` y
   `_auto_link_payment_methods`.
3. `account-journal-payment-method-lines-0515` — adopción de `BaseModel` por
   `account.journal`, los dos One2many calculados y
   `_get_available_payment_method_lines`.
4. `account-payment-method-line-field-0515` (existente) — los campos del pago
   (pasos 6-10) y, al final, `AccountPaymentMethodLine.unlink` (paso 11).

Cada una con prueba positiva, negativa y anulación. La 4 cierra la fila
pendiente del tramo B.

*Métrica:* símbolos y citas leídos en `odoo19c` y `grep` sobre nuestro árbol.
*Ciega a:* la conducta de los addons que extienden
`_get_payment_method_information` (`account_check_printing`,
`account_payment`): los mide cada unidad al portarse.
