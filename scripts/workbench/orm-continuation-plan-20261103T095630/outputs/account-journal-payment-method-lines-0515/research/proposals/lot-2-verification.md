# Informe: diseño de un control de "prosa heredada material" en `kaupamex-api`

Fue una investigación de solo lectura. No modifiqué archivos, no hice commits y no ejecuté pytest de integración ni migraciones. Hay cambios sin commitear de otra persona en `account*` y `tests/` (`git status --short`), y no los toqué.

## 1. Verificadores existentes

`ls scripts/check_*.py` da 33 scripts; leí la primera línea del docstring de cada uno. Ninguno detecta ordinales `#NNN` ni identidades `TASK-…`. El único `TASK-` dentro de un verificador es un comentario en `check_identifier_language.py:133`.

Tres verificadores ya cubren afirmaciones de ausencia o de estado fechado, y son los candidatos a reutilizar:

- **`check_stale_zero_claims.py`** (#228): vuelve a ejecutar los comandos `grep` citados en la prosa con "→ **0**" (regex `CITATION`, `:96`) y compara el resultado. Su tabla de episodios (`:24-31`) incluye H-API-982 ("``ir.actions.actions`` no está portado → existe") y H-API-983 ("``ir.model.data`` este árbol no tiene → existe"). Son exactamente la clase (b) que piden, pero solo los atrapa cuando la prosa cita su propio comando.
- **`check_bloqueo_vigente.py`**: resuelve el destino de una marca de bloqueo. Ya trae el resolvedor que (b) necesita: `declared_model_names()` (`:111`), `MODEL_NAME` (`:97`) y `reference_model_names()` (`:207`). Además fija dos criterios aplicables: una ruta resuelve solo en negativo (`:43-53`), y lo que no se puede resolver se publica como NO MEDIBLE, no como cero.
- **`check_bloqueo_declarado.py`**: valida la forma de la marca de bloqueo, sin resolver el destino.

**`check_reference_flow.py`** (363 líneas):
- **Alcance:** `in_scope` (`:317`) mide `src/orm/`, `(src/)?addons/x/models/*.py` y las migraciones. Deja fuera `__init__.py`, `wizard/`, `controllers/` y `src/tools`.
- **Clases de cambio:** `change_kind` (`:259-273`) clasifica así:
  - A: `src/orm`.
  - B: modelo con espejo en la referencia.
  - E: modelo sin espejo.
  - C: migración.
  - D: no es una clase de archivo. Sale de `changed_functions` vacío, porque el volcado AST quita el docstring (`:213-218`).
- **Citas:** `SYMBOL_CITATION` (`:77`, la forma `≙ ``X.n`` (``:N``)`) se resuelve por AST con dos líneas de holgura. `PATH_CITATION` (`:80`, la forma `odoo19c: ruta:N[-M]`) se resuelve por existencia de la ruta y rango. Solo se juzgan las citas nuevas: `citations(new) - citations(old)`, en `:178`.

## 2. Cableado en `.githooks/pre-commit`

Todos se aplican a los `.py` en staging de `src/`, `addons/` y `tests/`, sin migraciones. El orden es este:

1. `check_python_style.sh --increment`
2. `check_no_lazy_imports`
3. `check_canon_language` (en docs)
4. `check_silent_oks`
5. `check_identifier_language`
6. `check_identifier_reference_name`
7. `check_bloqueo_declarado`
8. `check_bloqueo_vigente --strict`
9. `check_escape_sequences`
10. `check_model_name_lookup`
11. `check_chain_combine --strict`
12. `check_addon_cycles`
13. `check_catalog_declaration`
14. `check_addon_names`
15. `check_addon_layout`
16. `check_urlconf`
17. `check_symbol_home --strict`
18. `check_addon_root --strict`
19. `check_chain_method_depends --strict`
20. `check_workbench --strict`
21. `check_field_class_attributes --strict` (solo si se toca `src/orm/fields*.py`; hace `exit 1` inmediato)
22. `check_stale_zero_claims --strict` (`exit 1` inmediato)
23. `check_write_path --strict` (un exit 2 se avisa y el commit sigue)
24. `check_reference_flow` (líneas 475-492; un exit 2 se avisa y el commit sigue; un 1 marca `EXIT_CODE=1`)

Todos bloquean, salvo el *skip* declarado cuando falta la referencia o el script.

## 3. Población medida

Comandos sobre `addons` y `src`, con `--include=*.py`:

| Clase | Conteo |
|---|---|
| `(tarea\|task) #N` | **467** líneas; de ellas, **0** llevan también un `TASK-` en la misma línea |
| `#NN` a `#NNNN` sueltos (filtrando colores hex) | 1351 (sobrecuenta) |
| `TASK-[A-Z]+-[0-9]{4}` | **139**; más frecuentes: TASK-API-0418 ×33, TASK-GEN-0060 ×20, TASK-API-0417 ×14 |
| "no existe" | 926 (incluye mensajes de usuario en tiempo de ejecución) |
| "NO están" | 35 |
| "no está portad" | 94 |
| "sin porte" | 1 |
| "pendiente" | 555 (incluye identificadores y etiquetas de datos) |

Ejemplos reales por clase:

- **Ordinal:**
  - `addons/hr/models/hr_employee.py:441` ("Sucesor: tarea #21.")
  - `src/config/settings/base.py:117` ("es la tarea #323")
  - `src/addons/base/models/res_partner.py:1272` ("tarea #112")
  - `addons/analytic/migrations/0006_so_line_from_sale.py:1` (#976)
  - `addons/account/migrations/0023_…:166` (#142)
- **TASK:**
  - `src/orm/models.py:1146` (TASK-API-0397)
  - `src/orm/models.py:765` (TASK-API-0190)
  - `src/orm/fields_textual.py:320` (TASK-GEN-0436)
  - `src/addons/base/models/res_partner.py:653` (TASK-GEN-0357)
  - `addons/account/models/account_analytic_line.py:319` (TASK-API-0418)
- **Ausencia:**
  - `addons/bus/models/ir_websocket.py:9` ("``pg_notify`` no existe en MariaDB"). Es prosa material caducada: el motor ya es PostgreSQL.
  - `addons/stock/models/stock_warehouse.py:157`
  - `src/addons/base/security/ir_model_access.py:20` ("aún no están portados")
  - `addons/product/models/product_combo_item.py:58` ("``ResCurrency._convert``, que no está portado")
  - `addons/account/demo/account_demo.py:790`
- **Pendiente:**
  - `addons/hr_homeworking/__init__.py:28` ("Wiring pendiente")
  - `addons/certificate/models/certificate.py:30`
  - Ruido que el control no debe marcar: `src/addons/base/migrations/0001_initial.py:67` (una etiqueta de datos) y `src/orm/environments.py:1551`.

**Medición de (b).** Usé un script ingenuo: el conjunto de `_name` (333 modelos) y una frase de ausencia con un modelo entre comillas dobles en la misma línea.
- Resultado: **186 pares**, de los que **59** nombran un `_name` que existe.
- Positivo candidato real: `addons/account_fleet/__init__.py:12` afirma que `account.automatic.entry.wizard` "no existe todavía en este puerto". Pero `addons/account/wizard/account_automatic_entry_wizard.py:138` lo declara: archivo añadido en `4c3a992e` (2026-10-29), y el `__init__` se tocó en `f2be473a` (2026-11-02) sin corregir la frase.
- Falsos positivos del enfoque ingenuo:
  - `addons/stock/models/stock_move_line.py:548`: "``stock.move`` aún no declara ``partner``" afirma la ausencia de un campo, no del modelo.
  - `addons/sale/models/sale_order.py:4`: "no existe un modelo "cart"; … es un ``sale.order``".
  - `addons/stock/models/ir_actions_report.py:1`: "NO PORTADO" se refiere a la extensión de `stock`, no a `ir.actions.report` (que existe en `src/addons/base/models/ir_actions_report.py:441`).

## 4. Propuesta: eje de prosa material

**Decisión de búsqueda previa: EXTEND, no MISSING.**
- El sitio natural es `check_reference_flow.py`, que ya separa lo nuevo de lo heredado: puede comparar las líneas de comentario y docstring de `old_text` y `new_text` por `tokenize` y AST, en vez de comparar el volcado.
- El resolvedor de modelos ya existe: se importa `declared_model_names()` y `MODEL_NAME` de `check_bloqueo_vigente.py`, no se reescribe.
- Hay que ampliar `in_scope` a `__init__.py`, `wizard/` y `src/tools`: la población de arriba muestra que la clase vive ahí.

**Eje (a), ordinal.** En cada línea de prosa nueva o modificada, un `(tarea|task|sucesor:?)\s*#\d+` o `\(#\d+\)` sin un `TASK-[A-Z]+-\d{4}` en la misma oración produce un hallazgo. Las 467 heredadas no se juzgan, porque solo cuenta lo nuevo.

**Eje (b), ausencia de modelo.** Frase de ausencia, con un sujeto gramatical que sea un modelo en `MODEL_NAME` y cuyo `_name` exista en el árbol: hallazgo.
- Hay que excluir la ausencia predicada de un atributo del modelo (patrón "``m`` aún no declara/tiene ``x``") y la negación existencial genérica ("no existe un modelo …").
- Lo que no se pueda clasificar se publica como NO MEDIBLE, con su denominador.

**Pruebas.**
- Positivas, tomadas del árbol real:
  - (a) la línea `hr_employee.py:441` como texto nuevo debe marcar.
  - (b) la línea `account_fleet/__init__.py:12` debe marcar.
- Negativas, también reales:
  - (a) `src/orm/models.py:1146` (TASK-API-0397) no marca.
  - (a) la misma frase de `hr_employee.py:441`, presente en `old_text`, no marca porque es heredada.
  - (b) `stock_move_line.py:548` no marca (ausencia de campo).
  - (b) `sale_order.py:4` no marca.
  - (b) `product_combo_item.py:58` no marca: es un método y no un modelo, así que es NO MEDIBLE.
  - Un objeto inexistente de verdad (un modelo de la referencia sin `_name` aquí) no marca. Es la regla D.1: el caso negativo apunta a un objeto real.
- **Anulación:**
  - Sustituir `declared_model_names()` por `set()` debe hacer caer exactamente el positivo de (b) y nada más.
  - Quitar la exclusión "aún no declara ``x``" debe hacer caer solo el negativo de `stock_move_line.py:548`.
  - Quitar el filtro de "solo líneas nuevas" debe hacer caer el negativo heredado de (a).
  - Restaurar, y borrar `__pycache__` antes de leer el veredicto.

## 5. Pruebas no discriminantes

1. **`tests/unit/tools/test_convert.py:98`:** `assert hasattr(XmlImport, '_scopes') or True` es una tautología literal: no puede fallar.
2. **`tests/unit/hr/test_hr_employee_category.py:18-20`:** `1 <= category.color <= 11` también pasa con un default constante `1`, así que no distingue `randint(1, 11)` de un literal. El mismo patrón aparece en `tests/unit/utm/test_utm.py:457` y `tests/unit/base/test_res_partner_category*.py`.
3. **`tests/unit/scripts/test_check_reference_flow.py:82-90`:** el diseño "nombra su prueba" usando como `TEST` la ruta de este mismo archivo. Como `design_covers` (`:252-254`) solo exige que la ruta citada exista, la condición de prueba no puede fallar: no mide que esa prueba ejerza el símbolo. Es una ceguera del verificador: de 116 referencias a pruebas en diseños, 110 existen, y el verificador no mira qué ejercitan.

## Lo que no se midió

- La suite completa de `tests/unit/scripts` no arranca sin Django: el `conftest` exige `DJANGO_SETTINGS_MODULE` y `--reuse-db`. Ejecuté solo las de `reference_flow`, `stale_zero` y `bloqueo_vigente` con `-c /dev/null --noconftest`: **82 passed**.
- Los conteos de "no existe" y "pendiente" incluyen cadenas de tiempo de ejecución y etiquetas de datos: son una cota superior.
- Los 59 pares de (b) no se verificaron uno por uno. Solo confirmé uno positivo (`account_fleet`) y tres falsos positivos.
