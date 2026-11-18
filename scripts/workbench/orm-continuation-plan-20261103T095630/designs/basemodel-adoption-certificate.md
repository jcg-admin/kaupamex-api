# Adopción de `BaseModel`: `certificate`

Creado: 2026-11-18T17:13:12 (UTC). TASK-API-0397, hija de `basemodel-adoption-0397`
(`basemodel-adoption-program.md`). Referencia: odoo-tools `abe4040ec1`,
Odoo 19 Community.

## El contrato de la fuente

- `class CertificateCertificate(models.Model)` con `_name`,
  `_description`, `_order = 'date_end DESC'` y `_check_company_auto`
  (`odoo19c: addons/certificate/models/certificate.py:20-24`).
- `class CertificateKey(models.Model)` con `_name = 'certificate.key'` y
  `_description = 'Cryptographic Keys'`
  (`odoo19c: addons/certificate/models/key.py:35-37`).
- `security/ir.model.access.csv`: dos filas, todo para
  `base.group_system`.

## Este árbol

- Los dos derivan de `TimeStampedModel`, no de `BaseModel`.
- `CertificateCertificate` declara sus cuatro atributos de clase;
  `CertificateKey` **no declara ninguno**: le faltan `_name` y
  `_description` (`atributos-de-clase-de-modelo.md`: si la fuente los
  declara, se portan todos).
- No hay `security/` ni `data` en el manifiesto.
- Divergencia de nombre que esta unidad **no** paga: los Many2one se llaman
  `private_key`, `public_key` y `company`; la fuente dice
  `private_key_id`, `public_key_id` y `company_id`. Renombrarlos toca
  columnas y a los consumidores de `account_edi_proxy_client`; es otra
  unidad.

Consumidores fuera del addon (`grep -rlE
"CertificateCertificate|CertificateKey|certificate\.(certificate|key)"`):
`account_edi_proxy_client` (modelo y `key.py`) y cuatro archivos de
`tests/`.

## Decisión

Forma de `utm`/`uom`: base `(models.BaseModel, TimeStampedModel)` en los
dos, cabecera de `CertificateKey` portada, CSV fiel declarado en `data`.
Cada lectura de un Many2one hacia uno de los dos que hoy compare con
`None` se porta a la veracidad de la fuente.

## RED

1. `issubclass(..., BaseModel)` para los dos; `CertificateKey._name ==
   'certificate.key'`.
2. Trinquete: `certificate` sale de `PENDING`.
3. Filas de ACL con sus identificadores externos.
4. Un usuario interno no crea `certificate.certificate`; uno de
   `group_system`, sí.
5. Consumidores derivados en verde.

## Ejecución (2026-11-18)

Símbolos:

- `CertificateCertificate` ≙ `odoo19c: addons/certificate/models/certificate.py:20`:
  base `(models.BaseModel, TimeStampedModel)`.
- `CertificateKey` ≙ `odoo19c: addons/certificate/models/key.py:35`: misma
  base, y `_name`/`_description` verbatim (`:36-37`).
- `addons/certificate/security/ir.model.access.csv`, copia fiel, en `data`
  (`odoo19c: addons/certificate/__manifest__.py:7-8`).

`makemigrations certificate --dry-run`: «No changes detected».

RED medido: 7 fallos (los cinco de
`tests/unit/certificate/test_certificate_basemodel_acl.py` y dos del
trinquete).

**Consumidor que cambió de conducta.**
`test_certificate.py::test_sign_raises_without_private_key` afirmaba
`row.private_key is None`; con `BaseModel` el Many2one vacío es un recordset
vacío. El código ya probaba por veracidad (`if not self.private_key:`,
como la fuente), así que se corrigió la prueba a `not row.private_key`.
Las dos `is not None` de `:172` y `:195` pasaban a ser siempre ciertas y
dejaban de discriminar: ahora afirman veracidad.

Subconjunto derivado (`grep -rlE
"CertificateCertificate|CertificateKey|certificate\.(certificate|key)|addons\.certificate" tests/`
más `tests/unit/account_edi_proxy_client` y el trinquete): 109 passed.

**Anulación.** Con los dos modelos devueltos a `TimeStampedModel` caen 5 de
24: las dos de herencia, la de acceso de `group_system` y las dos del
trinquete. Sobreviven la cabecera de la llave y las filas del CSV, que no
dependen de la base.
