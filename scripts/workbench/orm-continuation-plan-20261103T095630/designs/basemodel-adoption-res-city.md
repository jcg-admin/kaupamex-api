# `res.city` sobre `BaseModel`, con su ACL

Creado: 2026-11-18T14:00:55 (UTC). TASK-API-0397, unidad hija de
`basemodel-adoption-0397` (`designs/basemodel-adoption-program.md`).
Referencia: odoo-tools `abe4040ec1`, Odoo 19 Community.

## El contrato de la fuente

- `odoo19c: addons/base_address_extended/models/res_city.py:6-21`:
  `ResCity(models.Model)` con `_name`, `_description`, `_order` y
  `_rec_names_search` (`:7-10`), cuatro campos (`:12-15`) y
  `_compute_display_name` con `@api.depends('zipcode')` (`:17-21`), que
  **asigna** `city.display_name` por registro.
- `odoo19c: addons/base_address_extended/security/ir.model.access.csv`: dos
  filas — todo para `base.group_partner_manager`, lectura para
  `base.group_user` —, cargadas por el `data` del manifiesto
  (`odoo19c: addons/base_address_extended/__manifest__.py:17-18`).

## Este árbol

- `ResCity(models.RecordLoaderMixin, models.Model)`: los cuatro atributos
  de clase ya están; `_compute_display_name` **devuelve** el nombre y
  `__str__` lo consume (la docstring lo declara como divergencia de
  instancia).
- Sin `security/` ni `data` en el manifiesto: la ACL de la fuente no está
  portada.
- `base.group_partner_manager` existe (`src/addons/base/data/res_groups_data.py`).
- Consumidores en pruebas: `tests/unit/base_address_extended/` (dos
  archivos), `tests/unit/base/test_restrict_ondelete_country_todo.py`,
  `tests/integration/base/test_res_partner_field_registry.py`,
  `tests/unit/orm/test_delete_policy_contract.py`.

## Decisión

1. Base `(models.BaseModel, TimeStampedModel)`, la forma de `utm` y `uom`.
   Si `TimeStampedModel` añade columnas que la tabla no tiene, la migración
   lo dirá y se medirá.
2. `_compute_display_name` con la forma de la fuente: `@api.depends('zipcode')`
   y asignación por registro. `__str__` lee `display_name`.
3. `security/ir.model.access.csv` copia fiel, declarado en `data` del
   manifiesto (precedente `a40f3f22`, `designs/security-data-by-manifest.md`).
4. `base_address_extended` sale de `PENDING`.

## RED

- `ResCity` es `BaseModel`; las filas de ACL son las del CSV.
- Un usuario interno lee una ciudad y no la crea; un gestor de contactos sí.
- `display_name` lleva el código postal entre paréntesis cuando lo hay.

## Ejecución (2026-11-18)

- `ResCity(models.BaseModel, TimeStampedModel)`; `_compute_display_name`
  con `@api.depends('zipcode')` y asignación por registro
  (≙ `odoo19c: addons/base_address_extended/models/res_city.py:17`);
  `__str__` lee `display_name`. Sin migración: las columnas de auditoría ya
  existían.
- `addons/base_address_extended/security/ir.model.access.csv` copia fiel y
  declarada en `data` del manifiesto.
- **Lo que la adopción destapó en el consumidor `res.partner`.** La
  extensión de `base_address_extended` decidía con `is None`; un `Many2one`
  vacío hacia un `BaseModel` es un recordset vacío, y la fuente decide por
  verdad (`odoo19c: addons/base_address_extended/models/res_partner.py:49`,
  `:53`, `:61`). Los tres sitios pasan a la forma de la fuente
  (`_onchange_city_id`, `_onchange_country_id` y la política de dirección).
- **Lo que esta unidad no cierra.** La fuente devuelve
  `self._convert_to_write({...})` en `_convert_fields_to_values`
  (`odoo19c: odoo/addons/base/models/res_partner.py:657`); aquí se
  devuelve el valor crudo porque `ResPartner` aún no es `BaseModel` (no
  tiene `_convert_to_write`). Medido: portarlo hoy rompe 16 pruebas por
  `AttributeError`. Sucesor: la adopción de `res.partner` dentro del grupo
  `base` del programa, bajo TASK-API-0397.
- Premisas de prueba actualizadas: `city_id` vacío es un recordset vacío;
  `display_name` se lee del campo; dos lecturas de `city_id.name` en
  `test_res_partner_field_registry.py` van en `sudo()` porque esa prueba
  mide la escritura y no la ACL.
- Pruebas nuevas: `tests/unit/base_address_extended/test_res_city_basemodel_acl.py`
  (`test_res_city_is_a_base_model`,
  `test_the_acl_is_the_reference_csv_with_its_external_ids`,
  `test_an_internal_user_reads_a_city_but_cannot_create_one`,
  `test_a_contact_manager_creates_a_city`).
- **Desliz (2026-11-18T14:59:59).** La anulación del `data` del manifiesto se ejecutó con
  `--create-db` bajo `timeout 600`: el límite cortó la recreación de
  `orm_x2hokp_qa` (la base de las ejecuciones en serie) a mitad de sus
  migraciones. Las bases de los workers de F2 no se tocaron. Se reconstruye
  entera en segundo plano antes de seguir; una anulación que exige
  reconstruir la base va siempre en segundo plano, nunca con `timeout` en
  primer plano.

### Símbolos por archivo (para `check_reference_flow`)

- `ResCity._compute_display_name` ≙
  `odoo19c: addons/base_address_extended/models/res_city.py:18`. Prueba:
  `tests/unit/base_address_extended/test_partner_extension.py`.
- `_onchange_city_id` ≙
  `odoo19c: addons/base_address_extended/models/res_partner.py:48`,
  `_onchange_country_id` ≙
  `odoo19c: addons/base_address_extended/models/res_partner.py:59` y
  `country_enforce_cities` ≙ el campo relacionado de la fuente: deciden por
  verdad. Prueba: `tests/unit/base_address_extended/test_partner_extension.py`.
