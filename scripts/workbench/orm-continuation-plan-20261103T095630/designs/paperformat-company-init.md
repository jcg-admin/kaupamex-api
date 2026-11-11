# Unidad: formatos de papel de `base` y `res.company.init`

Diseño medido el 2026-11-11T01:48:01 sobre `52e38e84`, contra `odoo19c` (odoo-tools
`abe4040ec1`). Es la obligación de `res.company` del barrido de los cinco
`init` (`schema-and-translation-symbols-decision.md`).

## Contrato de la fuente

- `odoo/addons/base/data/report_paperformat_data.xml` (`noupdate="1"`,
  cargado por el manifiesto de `base`, `__manifest__.py:21`): tres
  registros. `paperformat_euro` (A4, `default=True`, márgenes 52/32/0/0,
  `header_spacing=52`, `dpi=90`, `css_margins=True`), `paperformat_us`
  (Letter, mismos márgenes) y `paperformat_batch_deposit`.
- `res.company.init` (`res_company.py:102-109`): en cada instalación o
  actualización, toda compañía con `paperformat_id` vacío recibe
  `base.paperformat_euro` si el XML-ID existe (`env.ref(…, False)`), y
  luego se llama a `super().init()`.

## Estado medido

- `base.paperformat_euro`: **no existe** como XML-ID en `orm_x2hokp_qa`.
- `ReportPaperformat` tiene todos los campos que el XML fija.
- `ResCompany.paperformat` existe; 0 compañías sin formato hoy.
- `ResCompany` no declara `init`.

## TRAE / CONSTRUYE

| Pieza | Mecanismo existente | Decisión |
|---|---|---|
| carga del dato | los datos de `base` los siembran módulos de `src/addons/base/data/` invocados desde una migración (`res_users_data.py` → `0106`; `res_groups_data.py`) con `_xmlid_row` | **TRAE**: `report_paperformat_data.py` + migración `0107`, mismo patrón; `noupdate` = crear si falta, no tocar si existe |
| reposición tras `flush` en pruebas | `_SEEDERS` de `tests/conftest.py` | **TRAE**: se añade la siembra |
| `init` | el gancho `init(using)` que `init_models` llama (s5) | **CONSTRUYE**: `ResCompany.init(cls, using=None)` que resuelve el XML-ID por `ir.model.data` del alias y asigna el formato a las compañías sin él |

## Pruebas (RED primero)

1. Tras `migrate`, `base.paperformat_euro` apunta a un `report.paperformat`
   A4 con los valores del XML.
2. Reejecutar la siembra no duplica ni pisa un registro editado (`noupdate`).
3. `ResCompany.init(using=alias)` asigna `paperformat_euro` a una compañía
   sin formato y no toca una que ya tiene otro.
4. Sin el XML-ID, `init` no falla y no asigna nada (`env.ref(…, False)`).
5. `init_models` sobre `res.company` ejecuta el paso 3.
6. Controles: sin la siembra cae 1; con `init` sin la guarda del formato
   existente cae la segunda mitad de 3.

## Resultado de la implementación (2026-11-11T01:59:00, sin commitear todavía)

- `src/addons/base/data/report_paperformat_data.py`: tabla `PAPERFORMATS`
  (los tres registros del XML, verbatim) y `seed_paperformats(apps, alias)`
  con semántica `noupdate` (`_existing`/`_xmlid_row` de `res_groups_data`).
- `src/addons/base/migrations/0107_seed_paperformats.py` (depende de 0106).
- `tests/conftest.py`: `paperformats_seed` en `_SEEDERS`.
- `ResCompany.init(cls, using=None)`: `update` sobre `paperformat__isnull`
  con el id de `base.paperformat_euro` resuelto por
  `IrModelData._xmlid_to_res_model_res_id`.
- `makemigrations base --check`: sin cambios.

Pruebas: `tests/unit/base/test_paperformat_seed.py`, RED
(`ModuleNotFoundError`) → GREEN 4/4.

Controles de anulación (`nullify.sh`, una mutación cada vez):

| Mutación | Cae | Veredicto |
|---|---|---|
| A: retirar el salto por XML-ID existente en la siembra | exactamente `test_a_second_seed_neither_duplicates_nor_overwrites` | discrimina |
| B: retirar `.filter(paperformat__isnull=True)` en `init` | exactamente `test_company_init_gives_the_euro_format_to_a_company_without_one` | discrimina |
| C: retirar la guarda `if res_id is None: return` | ninguna (4 passed) | mutante equivalente: `update(paperformat_id=None)` sobre compañías ya sin formato deja el mismo estado. Se conserva por fidelidad al `env.ref(..., False)` de la fuente; no es una obligación medible |

| D: retirar `model.init(using=using)` en `init_models` | exactamente `test_init_models_runs_the_company_init` | discrimina (punto 5 del diseño) |

Suite tras añadir el punto 5: 5/5. Se corrigió además el docstring de
`init_models`, que aún decía que `init` no estaba cableado.

*Métrica:* aserciones de la suite de la unidad con cada mutación.
*Ciega a:* la ejecución de `init` desde `orm.registry.init_models` sobre una
base distinta de la por defecto (lo cubre el patrón multidb, no esta suite).

## Corrección por `check_write_path` (2026-11-11T02:33:41)

El pre-commit rechazó el commit: `check_write_path` marcó
`ResCompany.init` con *«se salta un enganche que la fuente usa — nuestro:
por debajo · la fuente: por el enganche»*. La fuente escribe con
`company.write(...)`; el `QuerySet.update()` de la primera versión pasaba
por debajo del ORM (sin `write`, sin protecciones ni recómputos). Se
corrige, no se congela: `init` recorre las compañías sin formato leídas con
`using(alias)` y llama `write({'paperformat': ...})` en cada una.

Controles repetidos sobre la forma final:

| Mutación | Cae |
|---|---|
| B: `filter(paperformat__isnull=True)` → `all()` | exactamente `test_company_init_gives_the_euro_format_to_a_company_without_one` |
| C: retirar la guarda del XML-ID | exactamente `test_company_init_without_the_euro_format_assigns_nothing` |

C **deja de ser mutante equivalente**: sin la guarda, `get(pk=None)`
falla. La fila C de la primera tabla queda superada.

El gate completo de `bb515cdf` cubrió la versión con `update`; el
cambio posterior es el cuerpo de un método y se verifica con su subconjunto
derivado (`full-bb515cdf` no cubre esta forma, y su registro lo dice).

## El write de la fuente frente al nuestro, para vals = {paperformat_id} (2026-11-11T05:25:00)

Llamador: `init_models` (`odoo19c: odoo/orm/registry.py:741-752`) con
`env = Environment(cr, SUPERUSER_ID, context)`; `init` hace
`self.search([('paperformat_id','=',False)])`, `env.ref('base.paperformat_euro', False)`
y `company.write({'paperformat_id': ...})` por compañía
(`res_company.py:102-109`).

`ResCompany.write` de la fuente (`res_company.py:356-400`), rama por rama
para esta clave:

| Rama | Aplica | Por qué |
|---|---|---|
| `parent_id` → `UserError` | no | otra clave |
| activar `currency_id` | no | otra clave |
| `registry.clear_cache()` si toca `cache_invalidation_fields` | no | ese conjunto es `{'active','sequence'}` (`:340-345`) |
| `clear_cache('assets')` | no | `font`, colores, `external_report_layout_id` |
| archivar ramas | no | `active` |
| copiar delegados a ramas | no | `_get_company_root_delegated_field_names` = `['currency_id']` (`:111-119`) |
| `install_l10n_modules` | no | `country_id` |

Queda `BaseModel.write`: comprobación de campo, protección, recómputo de
dependientes y restricciones. Dependientes de `company.paperformat_id` en
la referencia (grep sobre base, web, base_setup): sólo
`base.document.layout.paperformat_id` (`addons/web/models/base_document_layout.py:61`),
un `related` de un modelo transitorio, no almacenado. Ningún calculado
almacenado depende del campo, así que la falta de `modified` en nuestro
`write` (obligación abierta de `orm-write-modified`, plan) no cambia el
resultado de esta escritura.

Nuestro camino: `RecordLoaderMixin.write` (`src/orm/models.py:2957`) →
`ResCompany.save` (`res_company.py:1041`, que sólo mantiene
`parent_path`). Alias: el registro se lee con `using(alias)` y, desde
`c5adb3ee`, se escribe dentro de `Environment(alias, SUPERUSER_ID, {})`
(`designs/init-alias-propagation.md`). Transacción: `init` no abre una
propia, como la fuente; corre en la del llamador (caso multidb con
`atomic` + rollback).

## Historia de verificación — tres implementaciones, tres veredictos

| Implementación | Escritura | Veredicto | Evidencia |
|---|---|---|---|
| 1 | `QuerySet.update()` | gate completo verde, **rechazada** por `check_write_path` en el pre-commit | `outputs/gates/full-bb515cdf` (cubre sólo esta forma) |
| 2 | `company.write()` sin entorno | subconjunto derivado verde; publicada en `d2b87463`; **falla con N>1** (`CompanyContextRequired`) | `outputs/gates/derived-company-init-write`; RED en `init-alias-propagation.md` |
| 3 | `company.write()` dentro de `Environment(alias)` | en verificación: ci-multidb y gate completo sobre `c5adb3ee` | `outputs/gates/ci-multidb-c5adb3ee`, `full-c5adb3ee` |

Los veredictos no se mezclan: el gate completo de la 1 no dice nada de la 2
ni de la 3.
