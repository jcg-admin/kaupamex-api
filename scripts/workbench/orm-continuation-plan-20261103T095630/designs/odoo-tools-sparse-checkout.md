# Liberación de almacenamiento en `odoo-tools` — sparse-checkout

Intervención 4.3.1, §6. Medido 2026-11-17 sobre `odoo-tools@abe4040ec1`
(rama `claude/bold-fermat-x2hokp`, árbol limpio, sin worktrees extra).

## Antes

| Medida | Valor |
|---|---|
| `du -sh odoo-tools` | 19 G |
| `.git` empaquetado (`count-objects`) | 1.33 GiB, 438 028 objetos |
| árbol: `18.x` / `19.x` / `16.x` | 9.3 G / 6.5 G / 1.7 G |
| disponible en `/` (`df --output=avail`) | 1 334 476 800 B |

Caso A de §6.4: la ocupación es el árbol materializado, no `.git`.
Sparse-checkout en modo cono; el contenido sigue en los objetos de `.git`
y se rematerializa sin red con `git sparse-checkout add <ruta>`.

## Qué se conserva y por qué

| Ruta | Consumidor medido |
|---|---|
| `19.x/odoo-19.0` | `odoo19c`, `scripts/reference_roots.py`; 120 archivos de api/thyrox |
| `19.x/odoo19-enterprise-main` | `odoo19e` |
| `18.x/odoo-18`, `18.x/odoo.enterprise` | `odoo18c`, `odoo18e` |
| `18.x/app-odoo-18.0`, `18.x/my-odoo-enterprise-18.0`, `19.x/industry-19.0` | fuente citada de puertos (`auto_backup`, …): se reconsulta |
| `docs`, `scripts`, `utils` | herramientas del propio repositorio |

## Qué se retira del árbol (sigue en `.git`)

`16.x`, `18.x/odoo-18.7z`, `18.x/almas_12_1`, `18.x/FE-CR-18.0`,
`19.x/Aquasachets-main`, `19.x/acr-commerce-suite-main`,
`19.x/install_odoo19`, `19.x/oerp-odoo-19.0` — `du -sc`: 8 842 560 KB.

Búsqueda de consumidores (`rg -F <nombre>` en kaupamex-api, kaupamex-docs,
thyrox, odoo-tools/scripts|utils): sólo citas de procedencia en prosa
(docstrings, `.rst`); ningún código construye esas rutas. `git status
--ignored` sobre ellas: 0 entradas, así que el sparse-checkout no deja
residuos sin seguimiento.

## Gobierno

`referencia-odoo-gobierna-las-decisiones.md` declara `odoo-tools` de sólo
lectura y que un checkout es un cambio. Esta operación la ordena la
intervención 4.3.1 §6; no escribe en el contenido versionado, no commitea,
no cambia la revisión ni la rama y es reversible con
`git sparse-checkout disable`.

## Después (aplicado 2026-11-17)

`git sparse-checkout set --cone 18.x/odoo-18 18.x/odoo.enterprise
18.x/app-odoo-18.0 18.x/my-odoo-enterprise-18.0 19.x/odoo-19.0
19.x/odoo19-enterprise-main 19.x/industry-19.0 docs scripts utils` → exit 0.

| Medida | Valor |
|---|---|
| `du -sh odoo-tools` | 11 G |
| disponible en `/` | 10 289 217 536 B |
| **recuperado** | **8 954 740 736 B** (≈ 8.3 GiB) |
| `git rev-parse HEAD` | `abe4040ec1` (sin cambio) |
| `git status --porcelain` | 0 líneas |
| `git fsck --connectivity-only` | sin errores |
| `scripts/reference_roots.py` | `odoo19c`, `odoo19e` presentes, 629 + 24 y 734 addons |
| diferencial `tests/unit/tools/test_misc_collections.py`, `test_set_expression.py` | 32 passed, exit 0 |

Se aplicó con F2 activo: F2 no lee ninguna ruta retirada y el disco al 97 %
(1.3 GB libres) amenazaba su propio log y sus bases.

Rematerializar una ruta: `git -C /home/user/odoo-tools sparse-checkout add
<ruta>`. Volver al árbol completo: `git sparse-checkout disable`.

*Límite:* no se tocó `.git` (1.33 GiB): un clon parcial ahorraría poco y
exigiría reconstruir el clon con espacio temporal que no había.
