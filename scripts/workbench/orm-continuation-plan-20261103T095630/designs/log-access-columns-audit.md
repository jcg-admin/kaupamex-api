# Log-access: la fuente inyecta cuatro columnas y el puerto lleva dos

Fecha: 2026-11-11T07:17:18 · TASK-API-0485 (obligaciones de `src/orm`),
bloquea filas de TASK-API-0397 y TASK-API-0485 del plan.
Origen: pregunta del ejecutor sobre `ProjectSaleLineEmployeeMap` y su base
`TimeStampedModel`: «analiza si en odoo-tools eso es correcto, porque puede
ser falso».

## Lo que declara la fuente (odoo-tools `abe4040ec1`)

- `odoo19c: odoo/orm/models.py:283-292`. Si `attrs.get('_log_access',
  self._auto)`, el metaclase añade **cuatro** campos por defecto:
  - `create_uid` = `Many2one('res.users', readonly=True)`;
  - `create_date` = `Datetime(readonly=True)`;
  - `write_uid` = `Many2one('res.users', readonly=True)`;
  - `write_date` = `Datetime(readonly=True)`.
- `:296` `LOG_ACCESS_COLUMNS = ['create_uid', 'create_date', 'write_uid',
  'write_date']`.
- `:4801-4805` `_create` fija las cuatro con `env.uid` y `cr.now()`.
  `:4384-4389` impide escribirlas salvo al superusuario durante la carga del
  registro. `:3960` `get_metadata` las lee.
- `odoo/orm/model_classes.py:267` `_log_access = _auto`: está activado por
  defecto en todo modelo con tabla. `:574` lo deriva de las columnas
  existentes en un modelo `_auto=False`.
- `odoo19c: addons/sale_timesheet/models/project_sale_line_employee_map.py:8`
  es `models.Model` sin `_log_access`, así que tiene las cuatro columnas.

## Lo que lleva el puerto (medido 2026-11-11)

| Columna de la fuente | Puerto | Medición |
|---|---|---|
| `create_date` | `created_at` (`TimeStampedModel`) | renombrada |
| `write_date` | `updated_at` | renombrada |
| `create_uid` | **ausente** | `grep -rlE "^\s+create_uid\s*="` en `src addons` → 0 |
| `write_uid` | **ausente** | idem → 0 |

`src/orm/model_classes.py:1107` redefine `LOG_ACCESS_COLUMNS =
['created_at', 'updated_at']` sin declarar las dos que faltan. Hay 239
archivos con herederos de `TimeStampedModel`.

DEC-09 (`kaupamex-docs: .../adoptar-arquitectura-server-service-odoo/
decisiones-adoptar-arquitectura-server-service-odoo.rst`) ratifica **dónde**
vive la base (`addons/base`) y difiere la auto-inyección. Su contexto cita las
cuatro columnas, pero **no decide** omitir `create_uid`/`write_uid` ni
renombrar las fechas. Por eso las dos ausencias son un porte parcial **no
declarado**, el desenlace que prohíbe `porte-completo-no-parcial.md`, y no
una divergencia decidida.

### Consumidores que dependen de las columnas ausentes

En los 25 módulos portados que la fuente también tiene, 89 archivos de la
fuente usan `create_uid` o `write_uid`: mail 23, base 12, stock 7, test_orm 6,
mass_mailing 5, account 5, website 4, sale 3, … (`$S/uid-usage.txt`, recuento
por módulo). Dos filas del plan ya están bloqueadas por esto:

- `attachment-record-access`: la regla «sin `res_id`, solo su creador»;
- `orm-models-get-metadata-reference-0485`: `get_metadata`.

*Métrica:* archivos `.py`/`.xml` de la fuente que nombran el literal, por
módulo portado.
*Ciega a:* un uso indirecto, como `_order = 'create_date desc'`, que sí se
cubre con `created_at`. Es un recuento de archivos, no de dependencias.

## Decisión de esta unidad

1. **Añadir `create_uid` y `write_uid` a `TimeStampedModel`.**
   - Son `Many2one('base.ResUsers', null=True, on_delete=SET_NULL)`: la fuente
     los declara sin `required` ni `ondelete`, así que su defecto es
     `set null` (`fields_relational.py:274-282`).
   - Llevan `related_name='+'`, porque la fuente no declara inverso.
   - Se fijan en `save()` desde `get_current_uid()`: `create_uid` solo en el
     alta y `write_uid` en cada escritura, como `:4801-4805` y `:4384-4396`.
   - No se fijan si no hay usuario en contexto: la fuente siempre tiene
     `env.uid`, pero aquí puede no haberlo, y entonces el valor queda `NULL`,
     sin inventar ninguno.
   - `LOG_ACCESS_COLUMNS` pasa a nombrar las cuatro, con las dos fechas bajo
     su nombre del puerto.
   - Genera una migración por app con modelos concretos: es aditiva, son
     columnas nulas y **no** reescribe ninguna FK existente.
2. **El renombrado `created_at` ↔ `create_date` NO se hace aquí.** Cambia el
   contrato de la API v2 con la UI y todas las consultas. Es una decisión del
   ejecutor y se registra como pendiente en «Lo que no cierra».
3. **Los modelos que no heredan `TimeStampedModel`** (los 90 que
   `timestamped_mixin.py` menciona) siguen sin log-access. Su vía fiel es la
   auto-inyección que DEC-09 difiere. Se censan en la prueba RED para que la
   cifra quede medida, no supuesta.

## `ProjectSaleLineEmployeeMap`: desenlaces caducados

| Desenlace declarado | Motivo declarado | Hoy |
|---|---|---|
| `sale_order_id` BLOQUEADO | `Project.sale_order` no existe | cierto: 0 coincidencias en `addons/sale_project/models` |
| `_domain_sale_line_id` BLOQUEADO | `_sellable_lines_domain` no existe | cierto: solo en prosa |
| `display_cost` BLOQUEADO | sin `env` ni semilla de UOM | a medias: `Environment.company` existe (`src/orm/environments.py:1115`); la semilla `product_uom_day` y `timesheet_encode_uom_id` siguen ausentes |
| `company_id`/`partner_id`/`cost_currency_id`/`existing_employee_ids` como `property`; `_compute_*` en un receptor `pre_save` | el ORM no tenía `related` ni calculados | **falso**: 133 archivos con `related=` y 106 con `store=True` en `addons/` |

La última fila es una divergencia de mecanismo cuya causa ya no existe. Se
corrige en una unidad propia (`designs/project-sale-line-employee-map-port.md`)
después de esta, porque los campos `related` y calculados de la fuente
dependen también de `company_id`, que lleva log-access como cualquier otro
modelo.

## Pruebas

- RED: un modelo concreto heredero declara las cuatro columnas de
  `LOG_ACCESS_COLUMNS`. Un `save()` con usuario en contexto fija
  `create_uid` = `write_uid` = usuario en el alta. Una escritura posterior con
  otro usuario cambia `write_uid` y no `create_uid`. Sin usuario, los dos
  quedan `NULL`.
- Control de anulación: retirar la fijación en `save()` hace caer exactamente
  los casos de valor, no el de declaración.
- `makemigrations --check` vacío tras generar las migraciones.
- Derivado: los directorios que nombran `created_at`/`updated_at`/
  `LOG_ACCESS_COLUMNS`, y el gate completo antes de publicar, porque el
  mecanismo es transversal.

## Lo que no cierra

- El nombre de las fechas (`created_at`/`updated_at` frente a
  `create_date`/`write_date`). Es una decisión del ejecutor: cambia la API v2.
  DESCONOCIDO con condición de cierre: su veredicto.
- La auto-inyección para modelos sin `TimeStampedModel` (DEC-09, diferida por
  el ejecutor).
- La protección de escritura de las cuatro columnas
  (`odoo/orm/models.py:4384-4389`). Requiere el camino `create`/`write`
  del ORM, no `save()`; queda como sucesor dentro de TASK-API-0485.
- No hay TASK propia: esta VM no escribe en el TaskStore de thyrox. Se
  registra bajo TASK-API-0485 en `plan.jsonl`.
