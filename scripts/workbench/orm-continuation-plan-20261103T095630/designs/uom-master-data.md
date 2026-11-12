# Datos maestros de `uom` y el cargador universal

TASK-GEN-0241, plan `uom-master-data-0241`. Autoridad: odoo-tools
`abe4040ec1`.

## Contrato de la fuente

`uom/__manifest__.py:13-18` declara en `data`, en este orden,
`data/uom_data.xml` (31 registros: 30 unidades y la precisión
`decimal_product_uom`), `security/uom_security.xml` (`group_uom`) e
`ir.model.access.csv` (dos filas sobre `model_uom_uom`), más
`views/uom_uom_views.xml`. `sale_timesheet` lee `uom.product_uom_day` (8 horas)
para convertir el costo por hora en costo por día.

## Lo que la carga destapó, en orden

1. `DecimalPrecision` no tenía `_load_records`: no adopta `RecordLoaderMixin`,
   que el docstring del mixin declara universal a través de
   `TimeStampedModel`. Medido sobre `apps.get_models()`: **98 de 450** modelos
   concretos no lo adoptan; 7 son del marco (admin, auth, contenttypes,
   sessions, token_blacklist); de los 91 restantes, cuáles tienen contraparte en
   la fuente está por medir (hay propios, como `base.CheckoutAttempt`). Aquí se
   corrige `DecimalPrecision`; la población es su propia unidad
   (`record-loader-universality-0485`).
2. `Uom` no declaraba ningún atributo de clase de la fuente; sin `_name` la
   reflexión no le daba `model_uom_uom` y el CSV no podía nombrarlo. Se portan
   los cinco (`_name`, `_description`, `_parent_name`, `_parent_store`,
   `_order`). `_parent_store` en un modelo que no es `BaseModel` no activa el
   mantenimiento del núcleo (`_maintains_parent_store`); `parent_path` lo
   sigue calculando `save()`, como en `hr.department`.
3. La fila sin `model_id` mataba la importación con
   `TransactionManagementError` en vez de devolver su error
   (designs/load-row-retry-savepoint.md).

## Lo que se porta

Los tres archivos de datos, copia fiel, y la clave `data` del manifiesto en el
orden de la fuente. `views/uom_uom_views.xml` no se carga: este árbol no sirve
el cliente web, como en el resto de los addons portados.

## Pruebas

`tests/integration/uom/test_uom_data.py` (4): la jornada de 8 horas con su
factor, las 30 unidades con su xml id y la precisión, la docena inactiva, el
grupo y las dos filas de acceso con sus permisos.

## Sigue

`hours_per_day` de `resource.calendar` como calculado almacenado editable, y
después `display_cost` con su inverso (`employee-map-display-cost-0241`).
