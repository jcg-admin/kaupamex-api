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

## Registro de ejecución

- Primer intento de commit rechazado por `check_reference_flow`: una variable
  local nueva (`product_keys`) cambiaba el AST de
  `AccountTaxFormula._eval_tax_amount_formula`; se envolvió la condición en
  paréntesis (AST idéntico, comprobado con `ast.dump`).
- **Desliz de proceso, corregido:** tras ese rechazo se lanzó F2 con el
  árbol sin commitear y el log nombrado `f2-c89d2fda`, una revisión que no
  contenía los cambios. Se detuvo a los segundos y se borró el log; no hay
  evidencia atribuida a `c89d2fda`. La F2 válida es la de `dbe18bb9`, lanzada
  con el árbol limpio tras el commit.
- Anulación: sin el mixin en `ResCountry`, el censo nombra exactamente
  `base.ResCountry` y el caso de carga falla (2 de 2).
- `makemigrations --check`: sin cambios. Suites de los archivos envueltos a
  mano: 388 passed.
- F2 de `dbe18bb9` se detuvo en
  `tests/integration/test_orm/test_index_method.py::test_a_django_model_without_basemodel_is_walked_by_its_fields`:
  su premisa `not hasattr(model, '_fields')` dejó de valer porque
  `RecordLoaderMixin` trae `FieldSqlMixin` y con él `_fields`, como todo
  modelo de la fuente. Lo que la prueba protege —`check_indexes` recorre un
  modelo de Django sin `BaseModel` por `model_field_registry`— sigue
  valiendo; la premisa pasa a `not issubclass(model, BaseModel)`.
- F2 de `99de4abe` se detuvo en
  `tests/unit/orm/test_adopt_schema_hooks.py::test_a_model_outside_the_loader_resolves_the_schema_hooks`:
  su premisa —`res.country` no hereda `RecordLoaderMixin`— ya no tiene
  miembros. Esa prueba documenta `adopt_schema_hooks`
  (`src/orm/model_classes.py:608-648`, `designs/adopt-schema-hooks.md`), que
  colgaba `_auto_init`, `_check_removed_columns`, `_add_sql_constraints` e
  `init` en los modelos sin el mixin: la compensación de la universalidad
  que esta unidad da por la MRO, como la fuente (`odoo19c:
  odoo/orm/models.py:3152-3268`). Con el mixin en todo modelo propio la
  función devuelve 0 siempre.

  **Decisión: se retira** (`adopt_schema_hooks`, `ensure_schema_hooks`, su
  receptor de `class_prepared` y la llamada de `src/addons/base/apps.py`).
  Dejarla mantendría una segunda vía al mismo contrato; el censo de esta
  unidad ya impide un modelo sin el mixin. Las pruebas conservan el
  contrato: todo modelo propio gestionado resuelve los cuatro métodos desde
  `RecordLoaderMixin` por MRO (salvo el `init` que declara
  `hr.employee.public`), y `init_models` sigue reconciliando `res.country`.
- F2 de `207c7ec3` se detuvo en el propio censo: 23 modelos de más. Medido
  importando todos los módulos de producto: **uno** es producto
  (`account.AccountInvoiceReport`, en `addons/account/report/`, que no se
  importa al cargar las apps y por eso faltó en el primer censo) y 22 son
  sondas que declaran las pruebas. Se le da el mixin al primero; el censo
  importa antes los `report` de cada addon y excluye los modelos de
  `tests/`. Anulaciones: sin el mixin en el informe, el censo lo nombra a
  él solo; sin la exclusión, `test_modified_engine.py` seguido del censo
  falla con sus sondas (`base.EngineOwner`, …).
