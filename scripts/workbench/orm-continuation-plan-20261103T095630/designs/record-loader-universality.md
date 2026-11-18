# `_load_records` en todo modelo concreto

Fecha: 2026-11-18. Unidad: `record-loader-universality-0485`
(TASK-API-0485). Borrador preparado en solo lectura mientras corría F2 de
`6ca06d18`; la decisión se toma al abrir la unidad.

## La fuente

`odoo19c: odoo/orm/models.py:5054-5140`: `_clean_properties`,
`_load_records_write`, `_load_records_create` y `_load_records` cuelgan de
`BaseModel`, así que **todo** modelo los tiene. El cargador de datos
(`odoo19c: odoo/tools/convert.py`) los llama sobre el modelo del
`<record>` sin preguntar.

## Aquí, medido

Censo regenerado por `probes/record_loader_census.py`
(`outputs/record-loader-census.tsv`, `5b0c3dbf`): 91 modelos concretos sin
`RecordLoaderMixin`.

| Cubo | Modelos | Cómo heredan |
|---|---|---|
| marco (Django, SimpleJWT) | 7 | sin contraparte |
| `BaseModel` sin `TimeStampedModel` | 2 (`account.AccountMoveLine`, `hr.HrEmployeePublic`) | `BaseModel` **no** incluye el mixin |
| `models.Model` directo | 82 | ni `BaseModel` ni `TimeStampedModel` |

- La universalidad de este árbol viene por `TimeStampedModel`
  (`orm/models.py:2721`, docstring de `RecordLoaderMixin`), cuyas bases son
  `TransactionClockSaveMixin, RecordLoaderMixin, FieldSqlMixin, …`.
- `RecordLoaderMixin` y `FieldSqlMixin` son clases llanas sin campos: añadir
  una como base no cambia el esquema ni genera migración.
- Llamadores de `_load_records`: `orm/models.py:3934,3953` (`load`) y
  `tools/convert.py:622,774` (`<menuitem>`, `<record>`). Un modelo sin el
  mixin muere con `AttributeError` en el primero que lo nombre.

## Opciones

1. **`BaseModel` adopta `RecordLoaderMixin`** — es donde la fuente los
   declara; cubre los 2 del segundo cubo y todo `BaseModel` futuro.
2. **Los 82 de `models.Model` directo adoptan el mixin en su declaración** —
   uno a uno, sin esquema. Es la vía que el docstring del mixin ya usa para
   `FieldSqlMixin`/`AccessManager` (tarea #96).
3. **El cargador cae al mixin para cualquier modelo de Django** — una sola
   pieza en `convert.py`/`load`, pero un modelo seguiría sin el método que la
   fuente le da, y `load` lo llama como método de clase.

Recomendación preliminar: 1 + 2. La 3 no da a los modelos el contrato de la
fuente: arregla sólo a quien carga.

## Pruebas (para cuando se abra la unidad)

`tests/unit/orm/test_load.py` (verify del plan) más un caso por cubo: un
modelo `BaseModel` sin `TimeStampedModel` y uno de `models.Model` directo
cargan un `<record>` y responden a `_load_records`. Una prueba de censo que
falle si un modelo concreto fuera del marco no tiene el mixin, con el
control de quitarlo a uno.

*Métrica:* clases de `apps.get_models()` sin el mixin, por cubo.
*Ciega a:* si cada modelo carga **bien** sus datos: el censo mide la
presencia del método, no su comportamiento sobre ese modelo.

## Decisión (al abrir la unidad, medido)

Desglose de los 84 por base directa: 69 `models.Model`, 7
`TransientModel` (`orm/models_transient.py:55`), 2 `BaseModel`, y 6 con un
mixin junto a `models.Model` (`DefaultGetMixin`, `MailThread`,
`AnalyticPlanFieldsMixin`, `SequenceMixin`) o heredando de un
`ResConfigSettings` que a su vez carece del mixin.

1. `BaseModel(DefaultGetMixin, RecordLoaderMixin, OrderMixin, Model)` y
   `TransientModel(TransactionClockSaveMixin, RecordLoaderMixin, Model)`:
   el mixin va **antes** de `OrderMixin` y después de
   `TransactionClockSaveMixin`, el orden de `TimeStampedModel`
   (`addons/base/models/timestamped_mixin.py:85-93`); otro orden no
   linealiza la MRO de un modelo que herede de los dos.
2. Cada clase restante pone `models.RecordLoaderMixin` justo antes de
   `models.Model` (el paquete `models` lo exporta).
3. Medido: los 84 ya tienen `_auto_init`, `init`, `_add_sql_constraints` y
   `_check_removed_columns` **en la propia clase**, así que añadir el mixin
   como base no los cambia. Sí cambia `save`: el de `RecordLoaderMixin`
   despacha los inversos anotados tras persistir (≙ `write`, `odoo19c:
   odoo/orm/models.py:4491-4493`) y para un modelo sin inversos es
   `super().save()`.

Prueba: `tests/unit/orm/test_record_loader_universality.py` — el censo (84
fallan antes) y `res.country` cargando un registro con su `xml_id`.
