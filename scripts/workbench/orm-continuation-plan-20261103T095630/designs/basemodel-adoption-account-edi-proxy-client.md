# Adopción de `BaseModel`: `account_edi_proxy_client`

Creado: 2026-11-18T18:09:48 (UTC). TASK-API-0397, hija de `basemodel-adoption-0397`.
Referencia: odoo-tools `abe4040ec1`, Odoo 19 Community.

## El contrato de la fuente

- `Account_Edi_Proxy_ClientUser(models.Model)`, `_name =
  'account_edi_proxy_client.user'`
  (`odoo19c: addons/account_edi_proxy_client/models/account_edi_proxy_user.py:25-33`).
- `security/ir.model.access.csv`: `group_system` todo;
  `account.group_account_invoice` sólo lectura.

## Este árbol

- `AccountEdiProxyUser(models.RecordLoaderMixin, models.Model)`: no es
  `BaseModel` y no hereda `TimeStampedModel` (sin columnas de
  `_log_access` declaradas: `grep -nE "create_date|write_date|create_uid"`
  → 0). Cambiar su base puede exigir esas columnas: se mide con
  `makemigrations --dry-run` antes de decidir.
- No carga el CSV. `account.group_account_invoice` existe aquí
  (`addons/account/security/account_security.xml:81`).
- Consumidores fuera del addon: `account_peppol` (cuatro modelos y su
  manifiesto) y dos archivos de `tests/`
  (`test_delete_policy_contract.py`, `test_webhook_token.py`). Sus
  lecturas de Many2one sobre el usuario se revisan contra la veracidad de la
  fuente.

## Decisión

Forma de `certificate`: base `BaseModel` (más `TimeStampedModel` si la
migración medida lo pide para las columnas de `_log_access`), CSV fiel en
`data`, consumidores portados a la condición de la fuente donde cambien
de conducta.

## RED

1. `AccountEdiProxyUser` es `BaseModel`.
2. Trinquete: `account_edi_proxy_client` sale de `PENDING`.
3. Las dos filas con sus identificadores externos.
4. Un usuario interno sin `group_account_invoice` no lee usuarios EDI.

## Ejecución (2026-11-18)

Medido antes de decidir la base: con `AccountEdiProxyUser(models.BaseModel)`
`makemigrations account_edi_proxy_client --dry-run` da «No changes
detected». `BaseModel` no añade columnas, así que no hace falta
`TimeStampedModel`; la base queda `models.BaseModel`, como la fuente
(`models.Model`).

Símbolos:

- `AccountEdiProxyUser` ≙
  `odoo19c: addons/account_edi_proxy_client/models/account_edi_proxy_user.py:25`.
- `security/ir.model.access.csv` y
  `security/account_edi_proxy_client_security.xml` (la regla
  multiempresa `company_id parent_of company_ids`), copia fiel, en `data`
  (`odoo19c: addons/account_edi_proxy_client/__manifest__.py:15-17`). El
  borrador de este diseño sólo contaba el CSV; la fuente carga también la
  regla, y el cargador de este árbol la acepta.

RED: 6 fallos (los cuatro primeros de la prueba nueva y dos del
trinquete). Prueba nueva: 5 casos, con la regla.

Subconjunto derivado (directorios de `tests/` que nombran el modelo,
`account_edi_proxy_client` o `account_peppol`: `tests/unit/account_edi_proxy_client`,
`tests/unit/account_peppol`, `tests/unit/orm`, `tests/unit/scripts`):
4125 passed, 39 skipped, 4 xfailed.

**Anulación.** Con la base devuelta a
`(models.RecordLoaderMixin, models.Model)` caen 5 de 26: la de herencia,
las dos de acceso y las dos del trinquete. Sobreviven las de filas del CSV
y de la regla, que miden la carga, no la base.
