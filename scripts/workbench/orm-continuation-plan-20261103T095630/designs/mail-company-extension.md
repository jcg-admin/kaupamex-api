# `mail/models/res_company.py`: lo que `mail` cuelga en la empresa

Creado: 2026-11-18T22:58:09 (UTC). TASK-API-0397, ítem del plan
`mail-company-extension-0397`. Referencia: odoo-tools `abe4040ec1`, Odoo 19
Community, LGPL-3: copia con adaptación y atribución. Primera unidad de la
cadena de `mail.alias` (`basemodel-adoption-helpdesk.md`, prerrequisitos).

Símbolo: `apply_mail_company_extensions`, que porta
`ResCompany._default_alias_domain_id`, `_compute_bounce`,
`_compute_catchall` y `_compute_email_formatted`.

## La prosa heredada, validada

| Afirmación | Medido | Veredicto |
|---|---|---|
| «`res.company.alias_domain_id` (…) no está portado» (`addons/mail/models/mail_alias_domain.py`, docstring) | `grep alias_domain src/addons/base/models/res_company.py` → 0 | **cierto** |
| «el modelo queda utilizable (…) pero la parte por-empresa está incompleta» | ídem | **cierto**; es esta unidad |

## La fuente

`odoo19c: addons/mail/models/res_company.py:7-62`, `_inherit = 'res.company'`:

- `alias_domain_id`: `Many2one('mail.alias.domain', 'Email Domain',
  index='btree_not_null')`, cuyo valor por defecto es
  `_default_alias_domain_id`: el primer dominio (`search([], limit=1)`);
- `bounce_email` y `bounce_formatted` (`_compute_bounce`), `catchall_email`
  y `catchall_formatted` (`_compute_catchall`): vacíos sin dominio, y si no,
  el correo del dominio y `formataddr((company.name, correo))`;
- `default_from_email`: `related='alias_domain_id.default_from_email'`;
- `email_formatted` (`compute_sudo`): el de `partner_id` si lo tiene, si no
  `catchall_formatted`, si no `''`;
- `email_primary_color` (`'#FFFFFF'`) y `email_secondary_color`
  (`'#875A7B'`).

## Decisión

`addons/mail/models/res_company.py` con `apply_mail_company_extensions()`,
invocada desde un `MailConfig.ready()` nuevo (la excepción #4 de
`no-lazy-imports.md`). Sigue el precedente de
`addons/purchase/models/res_company.py`:

- columnas (`alias_domain_id`, los dos colores) en `campos`, y su migración
  en `base`, que depende de la última de `mail` (precedente: `base` ya
  depende de migraciones de `account`);
- los calculados sin `store` como `propiedades`, porque `ResCompany` no es
  `BaseModel`.

`btree_not_null` es el índice parcial `WHERE alias_domain_id IS NOT NULL`
(`Field.index` ya lo traduce, unidad de índices).

## RED

1. una empresa nueva toma el primer dominio como `alias_domain_id`;
2. sin dominio, los cuatro calculados de rebote y catchall son `''`;
3. con dominio, `bounce_email` es el del dominio y `bounce_formatted` es
   `formataddr((nombre, correo))`, y lo mismo para catchall;
4. `default_from_email` es el del dominio;
5. `email_formatted`: el del partner si tiene correo, si no el de catchall;
6. los dos colores tienen el valor por defecto de la fuente.

Pruebas en `tests/unit/mail/test_mail_company_extension.py`.
