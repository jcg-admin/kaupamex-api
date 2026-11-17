# Unidad `account-journal-payment-method-lines-0515`

Cadena: `designs/payment-method-line-chain.md` §4, unidad 3, con `create` y
`_auto_link_payment_methods` traídos de la unidad 2
(`designs/payment-method-defaults.md`, «Reordenación»).

## Referencia

- `_default_inbound_payment_methods` / `_default_outbound_payment_methods`
  (`odoo19c: addons/account/models/account_journal.py:59-63`).
- `inbound_payment_method_line_ids` / `outbound_payment_method_line_ids`
  (`odoo19c: addons/account/models/account_journal.py:205-233`): One2many
  calculados y almacenados sobre `journal_id`, dominio por `payment_type`.
- `_compute_inbound_payment_method_line_ids` /
  `_compute_outbound_payment_method_line_ids` (`:462-504`).
- `_get_available_payment_method_lines` (`:1188-1203`).
- `AccountPaymentMethod.create` y `_auto_link_payment_methods`
  (`odoo19c: addons/account/models/account_payment_method.py:20-38`).
- Extensión de `account_payment`
  (`odoo19c: addons/account_payment/models/account_journal.py:11-14`):
  `super()` y luego filtra por `payment_provider_state != 'disabled'`.

## Medición previa (2026-11-17, sobre `9c8960bb`, sin commitear)

Cambiar sólo las bases a `models.BaseModel, TimeStampedModel`: sin cambio
de esquema (`makemigrations --check`). Subconjunto de los consumidores del
diario (12 directorios): **10 failed, 4484 passed**. Dos causas:

1. **ACL del diario por grupo** (6 casos). `account.journal` se lee sólo con
   `group_account_readonly`, `group_account_manager` o
   `group_account_invoice`; nuestro `ir.model.access.csv` es idéntico al de
   la fuente (`odoo19c: addons/account/security/ir.model.access.csv:54-56`).
   Con `BaseModel` la lectura de campos del diario pasa a comprobarse, y
   cuatro rutas leen el diario con un usuario sin esos grupos:
   `AccountMove._sequence_base` (`self.journal.code`),
   `CheckPrintingJournalSettings.effective_layout`,
   `prepare_print_checks`, `mark_as_sent` (y el endpoint de cheques: 403 en
   vez de 422/409). Antes de corregir hay que medir, ruta por ruta, si la
   fuente lee ese campo con el usuario (y entonces la prueba usaba un
   usuario que la fuente rechaza) o bajo `sudo`.
2. **La extensión de `account_payment`** (4 casos):
   `addons/account_payment/models/account_journal.py:40-50` hace
   `self.payment_method_lines.filter(...)` sin `super()` «porque no hay
   base». Con `BaseModel` la relación inversa es un recordset (sin
   `.filter`). La corrección es la de la fuente: la base en `account` y la
   extensión con `super()`.

## Tareas

1. Rutas del punto 1: medir cada una contra la fuente y corregir lo que
   diverja (prueba o código), sin `sudo` inventado.
2. Adopción de `BaseModel` por el diario.
3. Los dos One2many calculados, los métodos por defecto y
   `_get_available_payment_method_lines`; la extensión de `account_payment`
   pasa a `super()`.
4. `create` y `_auto_link_payment_methods` del método.
5. Migración: los dos One2many son almacenados por la línea (`journal_id`),
   sin columna en el diario; los diarios existentes reciben sus líneas por
   defecto con una migración de datos.

## Pruebas

`tests/unit/account/test_journal_payment_method_lines.py`: un diario bank
nace con una línea manual de entrada y una de salida; uno `general`, sin
líneas; `_get_available_payment_method_lines('inbound')` devuelve sólo las
de entrada; crear un método `multi` lo enlaza a los diarios elegibles; la
extensión de `account_payment` sigue descartando las pasarelas inactivas
(`tests/unit/account_payment/test_account_journal.py`).

## Ampliación (2026-11-17, tras la conciliación de la prosa heredada)

`designs/account-journal-inherited-prose.md` midió que la fuente declara
`unlink` en el diario (`odoo19c: addons/account/models/
account_journal.py:725-733`) (`:725-733`). Entra en esta unidad:

- `AccountJournal.unlink`: borra sus líneas de método de pago con su
  `unlink`, luego el diario, y después las cuentas bancarias que sólo
  usaban los diarios borrados.
- (Los tres atributos de clase de `:51-53` ya estaban declarados: medido
  después, no entran.)
- Migración `0043_compute_journal_payment_method_lines`
  (`ComputeStoredFields` sobre los dos One2many) para los diarios
  existentes.

Pruebas añadidas a `tests/unit/account/test_journal_payment_method_lines.py`:
`unlink` del diario borra sus líneas; la cuenta bancaria que sólo él usaba
se borra y la compartida con otro diario se conserva.

Verificación antes de esta ampliación (sin commitear): subconjunto de 13
directorios consumidores, 4543 passed, 40 skipped, 73 xfailed. Anulaciones
(copia y restauración byte a byte): sin la restricción de tipo cae
`test_a_general_journal_gets_no_lines`; sin distinguir `payment_type` caen
4; sin el auto-enlace cae 1; sin el filtro de la extensión cae
`test_excludes_line_of_inactive_provider`.
