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
