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

## Lo que entró en la unidad (medido)

- `addons/account/models/account_code_mapping.py`: `AccountCodeMapping`
  (`_auto = False`, `_table_query = '0'`, `Meta.managed = False`) con
  `create`, `_search` (con su función interna `get_accounts`, `:52-56`),
  `_compute_account_id`, `_compute_company_id`,
  `_compute_code` y `_inverse_code`; migración de estado
  `0058_accountcodemapping`; `AccountAccount.code_mapping_ids`.
- `One2many.__get__` (`src/orm/fields_relational.py`) deja de rehusar un
  inverso sin columna: el One2many se lee buscando en el comodelo, como
  `One2many.read` (`odoo19c: odoo/orm/fields_relational.py:940-967`).
- `BaseModel._field_to_sql` (`src/orm/models.py`) separa el nombre inválido
  del campo sin columna: `Invalid field` sólo si el campo no existe o es un
  reverso de Django (`ForeignObjectRel`), y `Cannot convert … because it is
  not stored` si existe sin columna (`odoo19c: odoo/orm/models.py:2920-2930`
  y `odoo/orm/fields.py:1215-1216`). Así el control
  `test_create_one2many_with_unsearchable_field` sigue rehusando con el
  mensaje de la fuente.

Divergencias de mecanismo, declaradas en el docstring del módulo:

- `_compute_code`/`_inverse_code` leen y escriben bajo
  `company_scope(company)`: aquí `env.company` sale de ese `ContextVar`, no
  del contexto `allowed_company_ids` que escribe `with_company`.
- `res.company` y `res.users` son modelos de Django: `company_id` se asigna
  con la instancia, y las empresas del usuario se filtran por `active` y se
  ordenan por `sequence, partner__name`.

Tests: `tests/unit/account/test_account_code_mapping_virtual.py` (3).
Anulaciones: con el guard repuesto caen las dos pruebas que leen o escriben
a través del One2many; con la rama antigua de `_field_to_sql` cae
exactamente el control del comodelo sin columna.

## Sucesor: los comandos sobre `code_mapping_ids`

`default_get` (`:724-725`), `copy_data` (`:903-923`) y `create`
(`:1033-1046`) de `account.account` escriben `code_mapping_ids` con
`Command.create({'company_id': …, 'code': …})`. Aplicar comandos One2many
sobre un comodelo sin tabla no está medido. Sucesor
`account-code-mapping-commands-0397`, con su prueba roja propia.

## Lo que este diseño no cierra

- Si Django vuelve antes con `update_fields=[]` vacío (el camino de `write`
  sobre un modelo sin tabla): sin medir; se mide en el primer test rojo.
- Los comandos de escritura x2many (`apply_one2many_commands`) con un inverso
  Many2one no almacenado: sin medir.

Ambos se cierran en la unidad, con su prueba roja, antes de implementar.

## Prueba heredada que fijaba la ausencia (descubierta en el F2 de 22898713)

`tests/unit/account/test_account_code_mapping.py::TestNoAccountCodeMappingModelExists`
afirmaba que ninguna app registra `accountcodemapping`: era la divergencia
declarada antes de MC2c-1. Con el modelo virtual portado esa afirmación es el
contrato viejo y se sustituye por el nuevo: `account.code.mapping` está
registrado bajo su nombre de la fuente, sin tabla (`_auto = False`,
`Meta.managed = False`), como `odoo19c: account_code_mapping.py` declara
`_auto = False` y `_table_query = '0'`. El subconjunto derivado omitió esa
prueba porque buscó el archivo nuevo y no el nombre del modelo
(`grep -rln "accountcodemapping\|account.code.mapping" tests/` da los dos
archivos).

## El id virtual supone empresas con pk < 10000 (F2 de df916a24)

`odoo19c: account_code_mapping.py:6,42,65` codifica el id como
`account_id * COMPANY_OFFSET + company.id` con `COMPANY_OFFSET = 10000` y lo
decodifica con `//` y `%`. Con un pk de empresa ≥ 10000 no falla: devuelve otra
cuenta y otra empresa (185096 → cuenta + 18, empresa 5096). Medido: las bases
de los workers del gate tienen `res_company_id_seq` entre 105509 y 185096
(`--reuse-db` no reinicia la secuencia); por eso la prueba pasó sola (base del
worktree, pks bajos) y falló en el F2.

Decisión de esta unidad:

- La codificación se conserva verbatim: el id virtual es contrato público.
- Nueva `_mapping_id(account_id, company_id)`, única constructora del id, usada
  por `create` y `_search`; rehúsa con `UserError` si
  `company_id >= COMPANY_OFFSET`. Divergencia declarada: la fuente no comprueba
  nada porque supone ids pequeños; aquí devolver filas de otra cuenta en
  silencio es peor que rehusar. Funciones cuyo cuerpo cambia: `create`,
  `_search`; nueva: `_mapping_id`.
- Pruebas: las empresas de `test_account_code_mapping_virtual.py` se crean con
  pk explícito libre bajo el límite; caso nuevo: una empresa con pk ≥ límite en
  las empresas del usuario hace que leer `code_mapping_ids` rehúse. Anulación:
  sin la comprobación cae exactamente ese caso.

DESCONOCIDO, decisión del ejecutor: una codificación válida para más de 9999
empresas (Kaupamex hospeda empresas L1 sin tope declarado) cambia el contrato
público del id. Condición de cierre: el ejecutor elige entre conservar el límite
de la fuente con esta guarda o fijar otra codificación.
