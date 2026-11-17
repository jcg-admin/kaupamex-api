# Bloque B — `account.payment.method.line`: restrict del método, set null del diario

Unidad: `orm-fk-delete-policy-contract-0515` (tramo B). Referencia:
odoo-tools `abe4040ec1`, alias `odoo19c:`.

## 1. Referencia

| Símbolo | Cita | Qué hace |
|---|---|---|
| `payment_method_id` | `odoo19c: addons/account/models/account_payment_method.py:104-109` | `required=True`, sin `ondelete` → `restrict` por defecto (`odoo19c: odoo/orm/fields_relational.py:274-282`) |
| `journal_id` | `odoo19c: addons/account/models/account_payment_method.py:117-121` | no requerido, sin `ondelete` → `set null` |
| `AccountPaymentMethod.unlink` | `odoo19c: addons/account/models/account_payment_method.py:90-92` | busca las líneas del método y las borra con su `unlink` **antes** de `super().unlink()` |
| `AccountPaymentMethodLine.unlink` | `odoo19c: addons/account/models/account_payment_method.py:150-162` | una línea usada por un `account.payment` no se borra: se le quita el diario |

Un `DELETE` crudo del método con líneas vivas falla por la clave `restrict`;
el borrado por el ORM (`unlink`) primero retira las líneas.

## 2. Binario (Django 6.0.5)

`on_delete=PROTECT` levanta `ProtectedError` en `Collector.collect` cuando un
hijo apunta al padre; `SET_NULL` escribe `NULL` en el hijo. `Model.delete()`
de instancia va directo al `Collector`: no pasa por `BaseModel.unlink`.

## 3. Nuestro estado (`94ceb687`)

| Fila | Hoy | Fuente |
|---|---|---|
| `AccountPaymentMethodLine.payment_method` | `CASCADE` | `restrict` |
| `AccountPaymentMethodLine.journal` | `CASCADE` | `set null` |
| `AccountPaymentMethod.delete` (sobrescritura de instancia) | borra las líneas con `QuerySet.delete` | no existe: la fuente lo hace en `unlink` |
| `AccountPaymentMethodLine.unlink` | no existe | conserva las líneas usadas por un pago |

`account.payment` **no declara** `payment_method_line_id` en este árbol
(`grep payment_method addons/account/models/account_payment.py` → 0), así que
la regla «usada por un pago» no tiene contra qué evaluarse.

## 4. Tareas

1. `payment_method` → `PROTECT`; `journal` → `SET_NULL`; migración.
2. Retirar la sobrescritura `delete` y portar `AccountPaymentMethod.unlink`
   tal como la fuente: borrar las líneas con su `unlink` y luego `super()`.
3. Añadir las dos filas a `CORRECTED` del contrato.
4. `AccountPaymentMethodLine.unlink` queda **bloqueado por algo medido**: falta
   `account.payment.payment_method_line_id`. Sucesor: unidad del plan
   `account-payment-method-line-field-0515` (portar el campo y luego el
   `unlink` de la línea).

## 5. Pruebas (`tests/unit/orm/test_restrict_ondelete_payment_method_line.py`)

- `unlink` del método borra sus líneas y el método (contrato de la fuente).
- `delete()` crudo del método con líneas vivas → `ProtectedError` (≙ el
  `restrict` de la clave en SQL).
- Borrar el diario deja la línea con `journal_id` nulo.
- Anulación prevista: con `CASCADE` de nuevo, cae el caso del `delete()`
  crudo; sin el `unlink` portado, cae el del `unlink`.
