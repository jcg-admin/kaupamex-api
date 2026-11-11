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
