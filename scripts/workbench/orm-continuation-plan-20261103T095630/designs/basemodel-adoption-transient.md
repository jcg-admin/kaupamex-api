# Adopción de `BaseModel`: los transitorios concretos

Creado: 2026-11-18T15:31:59 (UTC). TASK-API-0397, hija de
`basemodel-adoption-0397` (`basemodel-adoption-program.md`). Referencia:
odoo-tools `abe4040ec1`, Odoo 19 Community.

## El contrato de la fuente

`class TransientModel(Model)` (`odoo19c: odoo/orm/models_transient.py:10`),
y `Model` deriva de `BaseModel` (`odoo19c: odoo/orm/models.py:7049`). Un
transitorio es un `BaseModel`: tiene recordset, `check_access` y sus filas de
`ir.model.access.csv`.

## Este árbol

`TransientModel(TransactionClockSaveMixin, RecordLoaderMixin, Model)`
(`src/orm/models_transient.py`): `Model` es el de Django, **no** `BaseModel`.
Censo (`scratchpad/transient_census.py`, `apps.get_models()` concretos que
derivan de `TransientModel`), medido 2026-11-18: **8** clases, ninguna
`BaseModel`:

| app | `_name` | ACL de la fuente |
|---|---|---|
| account | `account.financial.year.op` | `addons/account/security/ir.model.access.csv:122` (aquí `:101`) |
| account | `account.setup.bank.manual.config` | `:123` (aquí `:102`) |
| base | `base.enable.profiling.wizard` | `odoo/addons/base/security/ir.model.access.csv:144` |
| base | `server.action.history.wizard` | `:126` |
| base_import_module | `base.import.module` | `addons/base_import_module/security/ir.model.access.csv:2` |
| base_install_request | `base.module.install.request` | `addons/base_install_request/security/ir.model.access.csv:2` |
| base_install_request | `base.module.install.review` | `:3` |
| base_sparse_field | (sin `_name`) `SparseFieldsTest` | — |

*Métrica:* subclases concretas, no proxy, de `TransientModel` en el registro.
*Ciega a:* los transitorios abstractos (los de `hr`, `hr_recruitment`,
`hr_work_entry`): no tienen tabla ni entran al censo, pero heredan el cambio.

## Decisión

La adopción es **de la base**, no clase a clase: `TransientModel` pasa a
derivar de `BaseModel`, como en la fuente. Cambiarlo en cada asistente
duplicaría la herencia que la fuente declara una vez.

- `class TransientModel(TransactionClockSaveMixin, BaseModel)`:
  `RecordLoaderMixin` ya lo trae `BaseModel`.
- Cada app con un transitorio concreto lleva su CSV fiel de la fuente y lo
  declara en `data`: `base_import_module` y `base_install_request` (no tienen
  `security/`); las filas de `account` ya existen.
- `base` no carga un CSV, pero declara las mismas dos filas en Python
  (`src/addons/base/security/ir_model_access.py:466-479`:
  `access.server.action.history.wizard` y
  `access.base.enable.profiling.wizard`, `group_system`, `(1, 1, 1, 0)`),
  idénticas a la fuente. Corrección del borrador de este diseño, que decía
  que `base` no tenía filas: medido después de escribirlo.

## RED

1. `issubclass(TransientModel, BaseModel)`.
2. `test_basemodel_reach.py`: `base_import_module` y `base_install_request`
   salen de `PENDING` y el trinquete lo exige.
3. Por cada asistente con consumidores en `tests/`, la suite derivada
   (`grep -rlE "base.import.module|base.module.install|server.action.history|enable.profiling|financial.year.op|setup.bank.manual"`)
   sigue verde: si un consumidor usaba la API de Django donde el recordset
   difiere, se porta la lectura de la fuente, no se envuelve.
4. Un usuario sin el grupo de la fila CSV no crea `base.import.module`
   (`base.group_system`, fila `:2`); con él, sí.

## Lo que esta unidad no cierra

- `account`, `base`: siguen en `PENDING` por sus otros modelos.
- `SparseFieldsTest` no tiene `_name`: el trinquete no lo mide.
- La carga de las demás filas de `base` (143 en la fuente) es una unidad
  propia del programa, no ésta.

## Ejecución (2026-11-18)

Símbolos:

- `TransientModel` ≙ `odoo19c: odoo/orm/models_transient.py:10`: ahora
  `class TransientModel(TransactionClockSaveMixin, BaseModel)`
  (`src/orm/models_transient.py`).
- `AccountFinancialYearOp` (`addons/account/wizard/setup_wizards.py`)
  declaraba `DefaultGetMixin` delante de `TransientModel`; con
  `BaseModel` en la base eso no tiene MRO consistente, y el mixin ya llega
  por `BaseModel`. Se retira de sus bases; la conducta no cambia.
- `addons/base_import_module/security/ir.model.access.csv` y
  `addons/base_install_request/security/ir.model.access.csv`: copia fiel,
  declarados en `data` como en la fuente
  (`odoo19c: addons/base_import_module/__manifest__.py:16-17`,
  `odoo19c: addons/base_install_request/__manifest__.py:13-14`).

Pruebas: `tests/unit/orm/test_transient_basemodel.py` (4) y el trinquete
`tests/unit/orm/test_basemodel_reach.py` sin `base_import_module` ni
`base_install_request` en `PENDING`.

RED medido antes de tocar código: 7 fallos, los cuatro de la prueba nueva y
tres del trinquete (las dos apps fuera de `BaseModel` y el conjunto
`PENDING`).

**Lo que la medición corrigió.** La prueba esperaba dos filas de
`base_install_request`; el CSV de la fuente trae **seis** (las dos de los
asistentes y cuatro de lectura sobre `ir.module.*` para `base.group_user`).
La copia es fiel, así que la prueba se corrigió para afirmar las seis.

`makemigrations --check --dry-run`: «No changes detected»; el cambio de
base no altera columnas.

**Consumidor que cambió de conducta, medido por el subconjunto derivado.**
La primera ejecución (36 archivos de `tests/` derivados por nombre de
modelo y `TransientModel`) dio 1 fallo de 732:
`test_setup_wizards.py::test_set_linked_journal_id_links_the_bank_account_to_the_journal`.
Con el asistente en `BaseModel`, `linked_journal_id` (comodelo
`account.journal`, ya `BaseModel`) se lee como recordset vacío, no como
`None`, y `if selected_journal is None` tomaba la rama de «diario elegido».
Se porta la condición de la fuente, `if not selected_journal:`
(`odoo19c: addons/account/wizard/setup_wizards.py:177`), y la de
`_onchange_new_journal_related_data` por la misma razón. Las demás
comprobaciones `is None` del archivo leen `res.partner.bank` (todavía fuera
de `BaseModel`) o el resultado de `.first()`, que sigue siendo `None`.

Subconjunto derivado tras el arreglo: 732 passed, 2 xfailed.

**Anulación.** Con `TransientModel` devuelto a
`(TransactionClockSaveMixin, RecordLoaderMixin, Model)` caen 5 de 22:
`test_a_transient_model_is_a_base_model`,
`test_the_import_wizard_is_for_system_users_only` y las tres del trinquete
(las dos apps y el conjunto `PENDING`). Sobreviven las dos de filas de ACL:
miden la carga del CSV, no la base, y es correcto que no dependan de ella.
La anulación del `data` de los manifiestos no se ejecutó: con `--reuse-db`
las filas ya cargadas persisten, y discriminarla exige recrear una base
(~53 min); queda cubierta por la base de F3 o por la anulación análoga de
res.city, que mide el mismo cargador.
