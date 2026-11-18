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
