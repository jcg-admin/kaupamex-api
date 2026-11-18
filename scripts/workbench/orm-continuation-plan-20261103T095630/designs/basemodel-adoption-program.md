# El programa de adopción de `BaseModel`

Creado: 2026-11-18T13:06:27 (UTC). TASK-API-0397, unidad paraguas
`basemodel-adoption-0397`. Referencia: odoo-tools `abe4040ec1`, Odoo 19
Community. Sigue a `hr-basemodel-dependencies.md` y
`basemodel-adoption-utm.md`, que fijaron la forma de una adopción.

## El contrato de la fuente

En la fuente no hay modelo que no sea `BaseModel`: `Model`,
`TransientModel` y `AbstractModel` derivan de él (`BaseModel` en
`odoo19c: odoo/orm/models.py:334`, `Model(AbstractModel)` en
`odoo19c: odoo/orm/models.py:7049`, `TransientModel(Model)` en
`odoo19c: odoo/orm/models_transient.py:10`), y `env[name]` devuelve
un recordset con `create`, `write`, `unlink`, `search` y `browse`.
Cada modelo trae además sus filas de `ir.model.access.csv`, que gobiernan
`check_access` en cuanto el modelo es `BaseModel`.

## La prosa heredada, validada

El plan declara `verify` =
`tests/unit/orm/test_basemodel_reach.py`: **no existe** (`ls` → no such
file). El paraguas no se podía asentar tal como estaba escrito.

## Medido

`probes/basemodel_adoption_census.py` → `outputs/basemodel-adoption-census.tsv`:
334 modelos concretos propios fuera de `BaseModel`. Los 188 sin `_name`
los clasificaron dos pasadas de solo lectura contra la referencia
(`outputs/basemodel-noname-part{1,2}.tsv`). Las dos tablas se verificaron por
separado: orden de entrada, siete campos por fila y cada cita resuelta a su
línea `_name`/`_inherit`. Resumen por app en
`outputs/basemodel-adoption-program.tsv`:

| Clase | Modelos | Qué exige |
|---|---|---|
| contraparte | **231** en 42 apps | `BaseModel`, atributos de clase de la fuente y su ACL (677 filas de CSV) |
| extensión | 42 | campos que la fuente añade con `_inherit` a otro modelo; aquí son tabla aparte. Su forma es otra unidad, no ésta |
| propio | 61 | sin contraparte: ni `_name` inventado ni ACL de la fuente (`atributos-de-clase-de-modelo.md`, «o ninguno») |

*Métrica:* clases de `apps.get_models()` concretas, no proxy, fuera de
`tests/`, que no son `BaseModel`.
*Ciega a:* qué API de recordset usa cada consumidor de esos modelos; se mide
por grupo antes de cambiar su base, como en `hr-basemodel-dependencies.md`.

## Decisión

1. **El `verify` del paraguas** pasa a ser el invariante de la fuente: todo
   modelo concreto propio que declara `_name` deriva de `BaseModel`
   (`tests/unit/orm/test_basemodel_reach.py`, parametrizado por app). Una
   contraparte sin `_name` entra en el censo cuando su unidad le porta la
   cabecera, que es parte de la misma adopción.
2. **Una unidad hija por grupo coherente**, con la forma ya probada en
   `utm`: la base pasa a `(models.BaseModel, TimeStampedModel)`, se
   declaran los atributos de clase de la fuente, y su
   `security/ir.model.access.csv` se copia fiel y se declara en el
   `data` del manifiesto. El grupo lo fijan las referencias entre modelos,
   no el addon (`hr-basemodel-dependencies.md`); `base` (68) se parte.
3. **Orden:** primero las apps pequeñas con ACL y sin consumidores
   `BaseModel` pendientes, para ampliar la superficie con riesgo bajo; las
   grandes (`base`, `account`, `stock`, `product`) después, partidas.
4. Cada hija se incorpora al plan con `bin/local_plan incorporate` cuando
   se va a ejecutar, con su censo por app como `verify`; el paraguas
   depende de que el censo global quede en cero.

## Lo que esta unidad no cierra

Las 42 extensiones (campos de `_inherit` portados como tabla aparte) son una
divergencia de forma con la fuente, no de `BaseModel`. Quedan bajo
TASK-API-0397 como **DESCONOCIDO**. Su condición de cierre: medir cuáles de
las 42 son tablas de relación de un `Many2many` (no son extensiones en
sentido estricto) y cuáles campos que deben volver al modelo extendido.
