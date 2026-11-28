# `country_ids` de `ir.module.module`

Sucesora de `designs/ir-module-versions.md`. TASK-API-0397.

## Contrato medido en la referencia

- `odoo19c: odoo/addons/base/models/ir_module.py:297`
  `country_ids = fields.Many2many('res.country', 'module_country', 'module_id', 'country_id')`.
- Su escritor es `_update_countries` (`:842-850`), que escribe la tabla
  `module_country` con SQL crudo sobre las columnas `module_id` y
  `country_id`.
- Su lector es `res.company._compute_uninstalled_l10n_module_ids`
  (`odoo19c: odoo/addons/base/models/res_company.py:207-241`), que une
  `module_country mc` por esas columnas.

## Lo que esta unidad hace

Declara el campo con la firma de la fuente; el `Many2many` del puerto acepta
`(comodel, relation, column1, column2)` (`orm/fields_relational.py:929-1010`),
así que la tabla y sus dos columnas salen con los nombres de la fuente. La
migración crea la tabla (`AddField`). El campo no tiene `related_name` propio
en la fuente: el reverso es `'+'`.

Lo que no cierra: `_update_countries` y el cómputo de `res.company` son las
unidades que lo consumen; quedan para el grupo de `_update_*` y para el
consumidor de `res.company`.

## Pruebas (RED)

`tests/unit/base/test_ir_module_country_ids.py`: la tabla `module_country`
con columnas `module_id` y `country_id`, y la lectura de `country_ids` desde
un módulo.

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `IrModule.country_ids` (`Many2many` por `module_country`, `module_id`/`country_id`) | `src/addons/base/models/ir_module.py` | `odoo19c: odoo/addons/base/models/ir_module.py:297` |
| docstring de `IrModule`: cobertura medida 25 de 31 | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:158-330` |
| migración `0157_ir_module_country_ids`: crea la tabla | `src/addons/base/migrations/0157_ir_module_country_ids.py` | `odoo19c: odoo/addons/base/models/ir_module.py:297` |
| `_serialize_many2many`: el serializador de Django lee un `Many2many` entre `BaseModel` por su gestor | `src/orm/models.py` | `odoo19c: odoo/orm/fields_relational.py:643-653` |

Medido al implementar: con la migración nueva, la serialización de la base de
pruebas de Django (`django/db/backends/base/creation.py:164`) murió con
`'ResCountry' object has no attribute 'select_related'`. El serializador
(`django/core/serializers/python.py:89`) toma `getattr(obj, field.name)` como
gestor, y entre `BaseModel` ese atributo es un recordset
(`_x2many_descriptor_get`, que porta `convert_to_record`). `country_ids` es el
primer `Many2many` almacenado entre dos `BaseModel` cuya tabla de dueño tiene
filas al serializar; el mismo defecto rompía `dumpdata` de cualquier modelo
así. El serializador lee ahora la relación por `orm.commands.related_manager`,
la autoridad que ya entrega el gestor de Django de un x2many.

Pruebas: `tests/unit/base/test_ir_module_country_ids.py` (2 casos; RED 2 de
2) y `tests/unit/orm/test_serialize_many2many_recordset.py` (1; RED 1 de 1).

Anulación (copia restaurada y comparada con `cmp`): sin instalar
`_serialize_many2many` vuelve el error de preparación de la base de pruebas.

Subconjunto derivado (35 objetivos: los archivos que nombran `IrModule`,
`ir.module.module`, los serializadores de Django o `country_ids`, más
`tests/unit/orm`): `8 failed, 4014 passed`. Las ocho, medidas:

- siete reconstruyen estados históricos de `IrModule` desde el modelo vigente
  (`test_module_category_migration.py`, `test_demo_failure_storage.py`), y el
  campo nuevo apunta a `base.rescountry`, que esos estados fabricados no
  contienen; se retira `country_ids` del estado fabricado, como ya se hacía
  con los campos posteriores a la migración que reproducen;
- `test_domain_in_required.py::test_the_count_over_a_fixed_population` cuenta
  los campos cuyo `null` discrepa de `is_not_null` y declara la cifra como
  evidencia fechada: `country_ids` es un `Many2many` sin columna propia, de la
  misma familia que `ir.filters.user_ids`; la cifra pasa de 36 a 37 con su
  razón.

Tras la corrección, esos tres archivos: `12 passed`.
