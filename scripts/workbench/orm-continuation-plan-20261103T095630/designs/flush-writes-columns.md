# El volcado escribe columnas, como `_write`

## Contrato de la fuente (odoo-tools `abe4040ec1`)

`_flush` (`odoo/orm/models.py`) recorre los campos sucios por modelo y llama
`_write_multi(vals_list)` (`:4524-4526`), cuyo docstring es *"Low-level
implementation of write()"*. `_write_multi` hace la aserción de longitud,
prepara `parent_path`, añade `write_uid`/`write_date` si el modelo lleva log
access, emite **un `UPDATE ... FROM (VALUES ...)` por lotes** con la expresión
de cada columna (traducción y dependencia de compañía incluidas) y termina con
`_parent_store_update()`. No llama `write`, ni `create`, ni ningún gancho: la
lógica de negocio y las automatizaciones viven en `write`/`create`, y las de
calculados en el parche de `_compute_field_value` de `base_automation`.

## Lo que hacía el árbol, y las dos sustituciones medidas

| Mecanismo | Lógica de `save()` del modelo | `pre_save`/`post_save` | `Field.pre_save` (`auto_now`, `write_uid`) | Fila ausente |
|---|---|---|---|---|
| `row.save(update_fields)` (antes) | **sí** | **sí** | sí | `DatabaseError` |
| `row.save_base(update_fields)` (candidata de esta unidad) | no | **sí** | sí | `DatabaseError` |
| `UPDATE` de columnas con los valores de `Field.pre_save` (esta corrección) | no | no | sí, invocado explícitamente | silencioso, como la fuente |

`save_base` (`django/db/models/base.py:925-990` instalado) envía `pre_save` y
`post_save`. En el árbol hay **16** receptores de `pre_save` y **17** de
`post_save` (medido con el registro de señales); varios son lógica de
negocio: `base_automation._dispatch_create_write` escucha **todos** los
modelos, y `account_fleet`, `l10n_mx`, `helpdesk`, `stock` reaccionan a
cambios de fila. Con `save_base` cada volcado los dispararía como si fuera
una escritura de negocio; la fuente no. **`save_base` no es equivalente a
`_write`.**

## Corrección

`_persist_columns(row, names)` en `src/orm/models.py`:

1. abre la memoria de reloj de la escritura (`SAVE_NOW`);
2. para cada columna nombrada toma su valor con `field.pre_save(row, False)`,
   que es donde viven `auto_now` (`write_date`) y el sello de `write_uid`
   (`LogAccessUserField.pre_save`), y luego `field.get_db_prep_save` lo hace el
   propio `UPDATE`;
3. emite `UPDATE` con `_base_manager.db_manager(alias).filter(pk=...)
   .update(...)`, en el alias de escritura de la fila
   (`router.db_for_write`); una fila borrada entre la lectura y la escritura
   no actualiza nada y no falla, como el `UPDATE` de la fuente;
4. en un `BaseModel`, retira las marcas de sucio de lo escrito.

La herencia multitabla de Django (sólo `base.IrActionsActWindowClose`) la
resuelve `QuerySet.update` con sus actualizaciones relacionadas.

## Consecuencia declarada, con sucesor

Las automatizaciones disparadas por el **recálculo** de un campo almacenado
(`make_compute_field_value` en la fuente,
`addons/base_automation/models/base_automation.py:909-940`) están declaradas
«bloqueadas» en el árbol porque «no hay motor de recómputo»; el motor ya
existe. Hasta ahora un efecto parecido llegaba de rebote por el `post_save`
del volcado. Su porte, como parche de `_compute_field_value`, queda en el
plan (`base-automation-compute-trigger-0485`).

## Pruebas

`tests/unit/orm/test_flush_write_contract.py`: el volcado no emite
`pre_save`/`post_save`, no ejecuta `save()` del modelo, y sella
`write_date`. Anulación: volver a `save_base` hace caer la de señales; volver
a `save` hace caer las dos primeras.
