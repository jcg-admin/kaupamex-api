# Investigación: consumidores y contrato de la línea de método en el pago

Unidad: `account-payment-method-line-field-0515`. Revisión base:
`286faed0`. Fecha: 2026-11-17. Investigador de sólo lectura; escribió su
informe directamente aquí y no ejecutó nada contra la base.

| Lote | Propuesta | Nivel |
|---|---|---|
| 0 | `proposals/lot-0-consumers-and-contract.md` | 3 — declarada, sin verificar |

## Filas abiertas (se conservan)

| Fila | Estado |
|---|---|
| ¿un diario de `objects.create` calcula sus líneas? | UNVERIFIED — el informe lo infiere del código (`src/orm/models.py:6014-6058`, `src/orm/fields_relational.py:556-559`); el coordinador lo mide con una prueba antes de implementar |
| sitios de creación de pagos: el diseño decía 9, el informe 8 | VERIFIED_CURRENT el informe: son 8; el noveno acierto del `grep` del diseño era la línea `class AccountPayment(` (`addons/account/models/account_payment.py:17`). Diseño corregido |
| `journal`, `company`, `currency` calculados en la fuente y planos aquí | MISSING en el diseño — decide si entra en esta unidad o en un sucesor |
| usuarios sin `partner` en el paso de datos de `partner` | UNVERIFIED |
| `apply_account_payment_extensions` sobre `BaseModel`; `makemigrations --check` | UNVERIFIED — exige ejecutar; después de la F2 |
| «Divergencia 1» de `account_check_printing` | OUTDATED al existir el campo; su reconciliación es un sucesor |

## Verificación del coordinador

- Sitios de creación: `grep -rnE "AccountPayment\.objects\.create|AccountPayment\.create\(|AccountPayment\("` sobre `tests addons src` da 9 líneas, 8 de creación y la declaración de la clase. Nivel 2.

El resto se añade al implementar cada paso.
