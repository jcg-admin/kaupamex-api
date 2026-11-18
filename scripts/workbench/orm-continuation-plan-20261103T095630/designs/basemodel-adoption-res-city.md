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
