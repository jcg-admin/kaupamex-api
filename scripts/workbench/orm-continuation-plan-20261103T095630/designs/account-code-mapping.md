# `account.code.mapping`: el modelo virtual de códigos por empresa (`account-code-mapping-0397`)

Sucesor declarado en `designs/account-account-mc2c.md` y en
`designs/account-account-write-branches.md`. TASK-API-0397.

## Lo que dice la referencia

`odoo19c: addons/account/models/account_code_mapping.py` (86 líneas,
LGPL-3). Modelo sólo de interfaz: `_auto = False`, `_table_query = '0'`, sin
filas. Sus registros existen por `browse` de ids sintéticos
`account_id * COMPANY_OFFSET + company_id` (`COMPANY_OFFSET = 10000`):

- `create` (`:40-47`) devuelve esos ids y asigna `code`, lo que dispara
  `_inverse_code`.
- `_search` (`:49-67`) exige una condición `('account_id', 'in', ids)` (si
  falta, `UserError` *"Account Code Mapping cannot be accessed directly. It
  is designed to be used only through the Chart of Accounts."*), y devuelve
  el producto cuenta × empresas del usuario (`sequence, name`) filtrado por
  el resto del dominio.
- `_compute_account_id` / `_compute_company_id` (`:69-76`) decodifican el id;
  `_compute_code` (`:78-81`) lee `account.with_company(company).code`;
  `_inverse_code` (`:83-86`) lo escribe con esa misma empresa.
- `account.account.code_mapping_ids = fields.One2many('account.code.mapping',
  'account_id')` lo expone, y `create`/`write` de la cuenta lo consideran en
  la unicidad del código.

## Por qué el archivo del puerto ya no vale

`addons/account/models/account_code_mapping.py` sólo es un docstring:
declaraba la premisa ausente porque la cuenta tenía una sola empresa (FK
`company`). MC2b, MC2c-1 y MC2c-2 la cumplieron: `company_ids` M2M, `code`
calculado sobre `code_store` por empresa raíz, sin columna `company`. Su
propia condición de cierre («si el proyecto adopta `company_dependent` de
verdad») se cumplió.

## Lo que el ORM del puerto ya tiene (medido, informe del 2026-11-25)

- `browse` → `_from_ids` construye registros sin fila ni `Model.__init__`
  (`src/orm/models.py:9750`, `:7466-7491`); `_origin` (`:10188`).
- Un calculado no almacenado se evalúa en memoria al leerse
  (`src/orm/fields.py:1837-1878`); `with_company` (`models.py:10229`).
- `_search` es sustituible y `search` pasa por él (`models.py:9032`,
  `:9161`, `:9204`); `Domain.map_conditions` (`src/orm/domains.py:490`),
  `filtered_domain` (`models.py:10448`) y `_as_query` (`models.py:10944`).
- `_auto=False` ≙ `Meta.managed=False`; `_table_query` se envuelve en
  `_table_sql` (`models.py:7259-7275`). Precedente: `hr.employee.public`.

## Lo que falta construir

1. **El modelo**: `BaseModel` con `Meta.managed=False`, `db_table`
   simbólico, `_table_query = '0'`, entrada de migración de estado, y su
   registro en `apps.py` (hoy lo excluye a propósito, `:31-37`).
2. **`One2many.__get__` con inverso no almacenado** (`src/orm/fields_relational.py:654-660`):
   hoy rehúsa con `ValueError` antes de `_read_one2many`. En la fuente el
   rechazo está en `Field.to_sql` (`odoo19c: odoo/orm/fields.py:1215-1216`),
   que sólo se alcanza si el comodelo no intercepta la condición en su
   `_search`. El guard tiene que dejar pasar al comodelo que sustituye
   `_search`. Es un cambio **transversal** del ORM espejado: obliga a la
   suite completa.
3. **El inverso al asignar**: `record.code = x` sobre un registro con id sólo
   marca el inverso pendiente (`fields.py:2112-2118`) y lo ejecuta `save()`
   (`models.py:3346-3390`); un modelo sin tabla no tiene `save`. `create`
   tiene que pasar por `write` o el `__set__` tiene que despachar inversos en
   un modelo sin tabla.
4. **Acceso**: filas de ACL para el modelo; sin medir cómo trata el puerto un
   modelo sin tabla en `check_access` (`models.py:9057`).

## Lo que este diseño no cierra

- Si Django vuelve antes con `update_fields=[]` vacío (el camino de `write`
  sobre un modelo sin tabla): sin medir; se mide en el primer test rojo.
- Los comandos de escritura x2many (`apply_one2many_commands`) con un inverso
  Many2one no almacenado: sin medir.

Ambos se cierran en la unidad, con su prueba roja, antes de implementar.
