# Contrato de identidad de modelo — `ir.model.model` guarda el `_name`

Fecha: 2026-11-23T08:04:52. TASK-API-0397. Prerrequisito de
`stock-security-data.md` (bloqueo registrado allí). Directiva del ejecutor del
2026-11-23: portar el contrato completo; sin puente en el cargador XML, sin
tocar `stock_security.xml`, sin inventar `_name`, clasificación exhaustiva
antes de cortar, y alcance por addon (seguridad, datos, transitorios,
informes, manifiestos, consumidores, pruebas, migraciones), con foco en
backend, ORM y seguridad.

## Contrato de la referencia

`'model': model._name` en `_reflect_model_params`
(`odoo19c: odoo/addons/base/models/ir_model.py:428`). Todo consumidor nombra
el modelo por ese valor: `ir.model.access`, `ir.rule` (que no tiene columna
propia: resuelve por `model_id.model`, `odoo19c: odoo/addons/base/models/ir_rule.py:24`),
`ir.model.data.model`, las acciones y los archivos de datos (`search=` sobre
`ir.model`, `ref="model_<_name con _>"`).

## Estado medido

Sondas: `probes/model_identity_census.py` (→ `outputs/model-identity-census-raw.tsv`)
y `probes/addon_contract_census.py` (→ `outputs/addon-contract-census.tsv`);
censo de lectores y escritores: `outputs/ir-model-model-census.md`.

### Clasificación (550 modelos del registro, `include_auto_created=True`)

| Categoría de la directiva | Cubo de la sonda | Modelos | Filas en `ir.model` hoy |
|---|---|---|---|
| 1 — `_name` contractual de la fuente | `reference-name` | 282 | 282 |
| 2 — fuente aplicable aún mal implementada | `reference-unnamed` (tabla o cita de la fuente) | 52 | 30 |
| 2/3 — por verificar uno a uno | `kaupamex`, `kaupamex-unproven` | 107 | 30 |
| 4 — interno de Django | `django-internal` | 7 | 0 |
| 5 — tablas automáticas de infraestructura | `infrastructure` | 102 | 97 |

Los 107 sin contraparte por nombre ni por tabla se verificaron modelo a
modelo, leyendo clase y fuente (`outputs/model-identity-own-classified.tsv`,
nivel 3: lo produjeron dos subagentes de sólo lectura; la sesión re-midió la
procedencia de `account_test.AccountingAssertTest` y las tres identidades
propias ya declaradas):

| Resultado | Modelos |
|---|---|
| 2 — extensión o porte de un modelo de `odoo19c` (tablas laterales de campos que la fuente añade por `_inherit`, portes sin `_name`) | 51 |
| 2 — contraparte sólo en otro árbol (`odoo19e`, `odoo18c`, `app_auto_backup`) | 5 |
| 3 — propio de Kaupamex que participa en el ORM | 47 |
| 3 — propio sin consumidores, ACL ni reglas medidos | 4 |
| 4 — interno de Django mal ubicado | 0 |

La identidad pública de los propios no se fija aquí. La convención verificable
es la de los tres propios que ya declaran `_name` (`return.request`,
`settings.static.page`, `support.ticket`): el `_name` se deriva de su tabla,
y `check_table_matches_name` (`src/orm/registry.py`) exige
`_name.replace('.', '_') == db_table`. Esa regla no fija dónde van los puntos
(`voucher_voucher`), así que cada propio recibe su identidad en su unidad, con
su segmentación comprobada contra la tabla.

### Escritura

`IrModel._reflect_models` (`src/addons/base/models/ir_model.py:796-857`)
recorre `apps.get_models(include_auto_created=True)`, guarda `model=<etiqueta
de Django>` y hace `bulk_create(update_conflicts, unique_fields=['model'])`.
`_reflect_model_params` porta las otras siete claves. Por eso las 97 tablas
intermedias tienen fila, que la fuente no les da.

### Consumidores en la base de pruebas

| Tabla | Por categoría del modelo |
|---|---|
| `ir_model_access.model_id` | 503 → cat. 1, 4 → propios |
| `ir_rule.model_id` | 84 → cat. 1, 4 con `model_id` nulo |
| `ir_model_data.model` | 1305 → cat. 1, 9 → cat. 2, 2 que ya guardan un `_name` (`mail.message.subtype`) |
| `ir_model_fields`, `ir_act_window`, `ir_act_report_xml`, `mail_message`, `ir_attachment` | vacías en esta base |
| modelos de la categoría 4 y 5 | 0 referencias |

*Métrica:* `GROUP BY` sobre la columna de modelo de cada tabla, cruzado con la
categoría de la etiqueta. *Ciega a:* bases reales con otros datos; por eso
toda migración que reescriba o retire filas comprueba sus referencias al
ejecutarse, no se fía de este conteo.

### Alcance por addon (109 addons aplicables)

La fuente declara 814 `_name` (fuera de `tests/`); cubiertos 299. Faltan 242
modelos, 142 transitorios y 130 abstractos. Datos de manifiesto: 1373 en la
fuente, 51 aquí; de ellos, 81 archivos de seguridad faltan en 49 addons, 204
de `data/`, 64 de informes y 38 de asistentes. Las 935 vistas y menús quedan
fuera de esta fase (no hay cliente web).

## Decisión por categoría

1. **Categoría 1:** `ir.model.model` guarda su `_name`.
2. **Categoría 2:** se porta el `_name` de la fuente en el modelo (unidad por
   addon, con su prueba). Mientras no lo declare, su fila conserva la etiqueta:
   no se le fabrica nombre en el reflejo.
3. **Categoría 3:** si participa en el ORM, identidad pública explícita según
   la convención verificada de Kaupamex (pendiente de la verificación de los
   107); si no participa, se conserva su fila actual hasta comprobar ACL,
   reglas, acciones, relaciones, datos y consumidores.
4. **Categoría 4:** fuera del registro contractual; hoy ya no tiene filas.
5. **Categoría 5:** la fuente no da fila a una tabla de relación. Sus 97 filas
   se retiran sólo con una migración que compruebe, en la base donde corre,
   que nada las referencia.

## Cortes

| Corte | Qué | Prueba discriminante |
|---|---|---|
| C1 | `orm.registry.identity_of(model)` —`_name` declarado o, mientras no lo tenga, la etiqueta— e `identity_for_key(key)`, su vuelta desde cualquiera de las dos formas; único punto de verdad junto a `name_of` y `model_by_key` (`odoo19c: odoo/addons/base/models/ir_model.py:428`) | `tests/unit/orm/test_model_identity.py`: un modelo de cada categoría; anulado `identity_of` a la etiqueta caen exactamente las dos pruebas que dependen del `_name` |
| C2 | lectores que esperan etiqueta (`django_model`, ACL, `ir_rule`, acciones, `base_automation`, `web`) resuelven por `registry.model_by_key`, que acepta las dos formas | las pruebas de ACL/reglas existentes con filas en las dos formas |
| C3 | el reflejo escribe `model_identity`; migración que reescribe `ir_model.model` y las columnas que cruzan por valor (`ir_model_data.model`, `ir_rule.model_name`, `ir_act_server.model_name`, `ir_act_report_xml.model`, `ir_model_fields.model/relation`) de etiqueta a `_name`, rechazando duplicados | `stock.picking` se encuentra por `('model','=','stock.picking')`; control negativo: la etiqueta deja de casar en `ir.model` |
| C4 | lectores que ya esperaban `_name` y estaban latentes (`registry.py:2447`, `IrRule._check_model_name`) | sus ramas se ejercitan |
| C5 | tablas automáticas sin fila (migración con comprobación de referencias) | el reflejo no crea filas `auto_created`; control negativo con referencia |
| C6+ | categoría 2 y 3, por addon | por addon |

`stock-security-data` se retoma tras C3.
