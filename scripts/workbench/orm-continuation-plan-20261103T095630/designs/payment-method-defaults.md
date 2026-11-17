# Unidad `account-payment-method-defaults-0515`

Cadena: `designs/payment-method-line-chain.md` §4, unidad 2.

## Referencia

- Registros `account_payment_method_manual_in` y `_out`
  (`odoo19c: addons/account/data/account_data.xml:129-138`): «Manual
  Payment», código `manual`, `inbound` y `outbound`.
- `_get_payment_method_domain(code, with_currency, with_country)`
  (`odoo19c: addons/account/models/account_payment_method.py:40-61`): sin
  código, `Domain.TRUE`; si no, `type in` los tipos de la información del
  código (por defecto bank, cash, credit), más moneda (`currency_ids`) y país
  (`country_id`) cuando la información los declara.

## Reordenación de la cadena (medida)

`create` y `_auto_link_payment_methods` (`:20-38`) buscan diarios con
`self.env['account.journal'].search(method_domain)`. `AccountJournal` deriva
hoy de `models.Model`: no tiene `search` con dominio (medido en el tramo B
sobre `AccountPaymentMethodLine`, `_check_field_access` ausente fuera de
`RecordLoaderMixin`). Esos dos símbolos pasan a la unidad 3, que adopta
`BaseModel` en el diario. Aquí quedan los registros y el dominio.

## Binario y nuestro estado

Precedente de siembra: `addons/account_check_printing/data/
check_payment_method.py` (`seed_check_payment_method`, migración `0002`):
módulo de datos con el registro y su `ir.model.data` (`noupdate=True`),
idempotente, sobre los modelos históricos. Se reutiliza esa forma.

`Domain` existe en `src/orm/domains.py` (`Domain.TRUE`, `&`, `|`).
`_get_payment_method_information` ya existe (sólo `manual`).

## Cambio

- `addons/account/data/payment_methods.py`: los dos registros y
  `seed_manual_payment_methods(apps, alias)`.
- Migración `0042_seed_manual_payment_methods` con `RunPython`.
- `AccountPaymentMethod._get_payment_method_domain` como en la fuente.

## Pruebas

`tests/unit/account/test_payment_method_defaults.py`: los dos registros
existen con su identificador externo; la siembra es idempotente;
`_get_payment_method_domain('manual')` selecciona un diario bank y descarta
uno de tipo `general`; sin código devuelve `Domain.TRUE`. Anulación: sin la
cláusula de `type`, cae el caso del diario `general`.
