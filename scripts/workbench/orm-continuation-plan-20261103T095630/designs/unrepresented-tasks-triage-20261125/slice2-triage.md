# Triaje de TASK sin unidad — rebanada 2

Lectura solamente. Ninguna prueba ejecutada. Raíz del puerto: `api` = `/home/user/kaupamex-api`;
`docs` = `/home/user/kaupamex-docs/source/gestion/pm/api/iniciativas/completar-raiz-orm`.
Confirmado: ninguno de los 15 ids aparece como `taskId` de una unidad en `plan.jsonl` ni en `candidates/`
(`plan.jsonl:202-203` trae `TASK-GEN-0241`, otra tarea).

| TASK | veredicto | razón en una línea | evidencia |
|---|---|---|---|
| TASK-API-0115 | CLOSED | el motor de `@api.depends` ya existe (grafo, `modified`, recómputo) y tiene pruebas | api: src/orm/models.py:5118, :5286; tests/unit/orm/test_modified_engine.py |
| TASK-API-0216 | NOT-ORM | gate de nuestro registro `__all__` de tipos; sin fuente en odoo19c; criterio clases-only obsoleto | api: src/orm/fields.py:128-146; docs: hallazgos/../H-API-616 |
| TASK-API-0241 | NOT-ORM | barrido documental de citas 18e sin alias | docs: analisis-contrato-de-basemodel-trae-o-construye.rst:121-123 |
| TASK-API-0282 | CLOSED | `_search` filtra `active` y hay prueba; "ningún manager" no es obligación de Odoo | api: src/orm/models.py:9060-9068; tests/unit/orm/test_search_returns_query.py:70 |
| TASK-API-0381 | NOT-ORM | resolución de base por petición HTTP multi-db; `http.db_monodb` fue retirado en Odoo 18/19 | api: src/service/db.py:182-191; addons/web/controllers/session.py:63-77 |
| TASK-API-0403 | UNIT | falta `Id.__set__`; mecanismo y marca de construcción ya existen | api: src/orm/models.py:11348-11353; src/orm/fields.py:1481-1490 |
| TASK-API-0408 | NOT-ORM | censo de citas `src/gates` en cinco clones tras mudanza; es documentación | docs: hallazgos/hallazgo-H-API-1097-...:62-66 |
| TASK-API-0413 | NOT-ORM | higiene de fixtures de prueba; helper ya existe y falta adoptarlo en 8 archivos | api: tests/fixtures/probe_tables.py:1-30 |
| TASK-API-0422 | UNIT | falta el check de create de la fuente para Many2one con `bypass_search_access` | api: src/orm/models.py:924-928, :995-1022; odoo19c: odoo/orm/models.py:4686-4687 |
| TASK-API-0478 | NOT-ORM | cableado de CI (checker, checkout de odoo-tools); dueño `codex-ci-local` | docs: hallazgos/hallazgo-H-API-1151-...:16-17, 48 |
| TASK-API-0492 | NOT-ORM | alcance `src/tools/zeep/wsdl`: reexportación de SOAP, ya fiel | api: src/tools/zeep/wsdl/utils.py:1-2 |
| TASK-API-0512 | CLOSED | leer un Many2one diferido ya no marca recómputos; prueba y anulación | api: commit 051ca50e; tests/unit/orm/test_many2one_deferred_read.py:41 |
| TASK-GEN-0060 | CLOSED | almacenamiento jsonb por idioma de `translate=True` construido y probado | api: src/orm/fields_textual.py:737-900; tests/unit/orm/test_translated_char.py |
| TASK-GEN-0391 | UNIT | `ir.actions.server` aún guarda `model_name` Char; `ir.rule` ya tiene FK | api: src/addons/base/models/ir_actions.py:1118, :1590-1597; odoo19c: ir_actions.py:635-638 |
| TASK-GEN-0633 | BLOCKED | triaje de 64 rojos exige ejecutar `tests/unit/orm` (prohibido ahora) y tiene dueño ajeno | docs: progreso/bitacora-continuidad-...:173-180 |

## TASK-API-0115 — CLOSED
La tarea era "construir el motor de `@api.depends`" (H-API-363: decorador inerte, 0 lectores). Hoy `decorators.py:93-123`
guarda `_depends`, `registry._DerivedCollector` (src/orm/registry.py:737) construye el grafo, y
`modified`/`_modified_triggers`/`_recompute_field` portan `odoo19c: odoo/orm/models.py:6756-6959`
(src/orm/models.py:5048, :5093, :5118, :5286). `recursive` se consume en `fields.py:4573-4576, :5331, :5530`
y `models.py:5173`. Prueba: `tests/unit/orm/test_modified_engine.py` (16 casos, cabecera "Cierra el motor").
La bitácora que la marca como DECISIÓN es anterior (docs: progreso/bitacora-abastecimiento-...:137).
SIN VERIFICAR: que las 26 anotaciones de H-API-363 hoy disparen todas (no se ejecutaron pruebas).

## TASK-API-0216 — NOT-ORM
El gate propuesto ("`__all__` solo clases `Field`") protege el vocabulario `ttype` de nuestro `ir_model.py`, no una
obligación de odoo19c. H-API-616 ya fija que el criterio histórico no vale: 13 de los 20 nombres de `__all__` son
fábricas (docs: hallazgos de completar-primitiva-domains/H-API-616, sección "Revalidación", y tareas:1103).
Si se quisiera, el trabajo es una prueba de 10 líneas en `tests/unit/orm/` que reconcilie fábricas y descriptores
(`One2many`); no tiene obligaciones `odoo19c:`, por eso no se propone unidad.

## TASK-API-0241 — NOT-ORM
"Barrer artefactos que midieron 18e sobre la raíz sin alias": trabajo de documentación y análisis. La bitácora
declara que no es equivalente a corregir la rama de ejecución (analisis-contrato-...:119-124).

## TASK-API-0282 — CLOSED
Título original: "active existe en 35 modelos y ningún manager lo filtra" (hallazgo de `account`). En Odoo el filtro
vive en `search`, no en un manager: `_search` agrega `active = True` salvo `active_test=False` o condición explícita
sobre el campo (src/orm/models.py:9060-9068). Prueba: `test_active_test_filters_archived_unless_asked`
(tests/unit/orm/test_search_returns_query.py:70). SIN VERIFICAR: si se quiere además un manager de Django que filtre;
no es obligación de odoo19c y la bitácora de managers (docs: progreso/bitacora-vaciado-fisico-...:43) la deja sin dueño.

## TASK-API-0381 — NOT-ORM
`db_list_for_host`/`db_monodb` existen (src/service/db.py:173-191) pero la propia fuente declara que `http.db_monodb`
se removió en Odoo 18/19 (:185). Elegir la base por host es aislamiento multi-db de Kaupamex (iniciativa
`implementar-aislamiento-multi-db-per-company`), no ORM de Odoo 19 Community. Condición: lo decide el
ejecutor en esa iniciativa; no hay `odoo19c:` que citar.

## TASK-API-0403 — UNIT
`Id.__set__` de la fuente (`odoo19c: odoo/orm/fields_misc.py:113-114`) no se porta porque convertiría a `id` en
descriptor de datos y rompería `Model.__init__` (src/orm/models.py:11348-11353, H-API-1091). La vía que el hallazgo
nombra ya existe: `_model_init_marking_the_load` marca `_orm_building` (src/orm/fields.py:1481-1490) y
`__set__` de campos ya lo consulta (fields.py:1631, :1638). Unidad acotada: `__set__` que rehúsa fuera de la
construcción, con medición previa del coste en el camino caliente. Candidato: `candidate-orm-id-set-protection-0403.jsonl`.
Riesgo: el coste es una decisión; la unidad exige medir y puede cerrar con "se declina, medido".

## TASK-API-0408 — NOT-ORM
Censo de referencias a `src/gates` tras mover a `src/verify`. `git grep -l "src/gates"` da 13 archivos en api y 160 en
docs (0 en db, server, ui). Es mantenimiento documental/herramientas, sin obligación Odoo.

## TASK-API-0413 — NOT-ORM
Fixtures de pruebas que no sobreviven a una ejecución cortada (H-API-1104). Ya existe
`tests/fixtures/probe_tables.py` (retira la tabla sobrante antes de crear) y lo usan 6 archivos de prueba
(commit 8e9cba96). Siguen con `create_model` directo: tests/unit/orm/test_missing_recompute.py,
test_field_index_not_null_and_trigram.py, test_relational_reconstruction_persistence.py, tests/unit/modules/*(2),
tests/unit/hr/test_payroll_calendar_migration.py, tests/unit/website_sale/test_salesteam_migration.py,
tests/integration/tools/test_sql_ddl_port.py. Es higiene de pruebas; su cierre es adoptar el helper, sin `odoo19c:`.
(Los commits que `git log --grep=0413` devuelve son de TASK-GEN-0413, otra tarea.)

## TASK-API-0422 — UNIT
La fuente, en `create`, comprueba lectura del comodelo para cada Many2one con `bypass_search_access` fuera de `su`
(`odoo19c: odoo/orm/models.py:4686-4687`). Nuestro `create` lo declara no portado "porque ningún campo declara ese
atributo" (src/orm/models.py:924-928). Esa premisa caducó: `inherits.py:256-263` marca todo campo delegado con
`bypass_search_access`, y los campos relacionales lo tienen (fields_relational.py:292, :867-878). El título habla de
"propagar a padres `_inherits`": en la fuente es este mismo check, que alcanza al FK delegado.
Candidato: `candidate-orm-create-bypass-search-access-check-0422.jsonl`. Riesgo: creaciones sin usuario en pruebas
y addons pasarán a ACL fail-closed (precedente en la bitácora create-por-contenido, "22 rojos").

## TASK-API-0478 — NOT-ORM
Sucesor de H-API-1151/1153/1154: la cualificación del checker `scripts/check_python_style_increment.py` hereda el
índice temporal del commit y falta cablear el checkout de odoo-tools en CI. Dueño `codex-ci-local`
(docs: progreso/bitacora-abastecimiento-...:134-137). No hay fuente en odoo19c.

## TASK-API-0492 — NOT-ORM
Es una de las ocho TASK de alcance 0485..0492, una por directorio espejo (docs: progreso/bitacora-reconciliacion-...:96-101);
la 0492 corresponde a `src/tools/zeep/wsdl`. Su única obligación pendiente (`obligation_classification.tsv`,
`src/tools/zeep/wsdl/utils.py`, `mirror=yes`) es un reexport idéntico al de `odoo/tools/zeep/wsdl/utils.py`
salvo el docstring y un `noqa` (diff leído). Es una biblioteca SOAP vendorizada, no ORM. Bastaría reclasificarla como
`match` en el inventario.

## TASK-API-0512 — CLOSED
H-API-1210: leer un Many2one diferido marcaba `tocompute`. El commit 051ca50e marca la carga como `building` (fields.py
~1810-1823) y añade `tests/unit/orm/test_many2one_deferred_read.py` (3 casos; el primero afirma que la lectura no marca
nada, el tercero que asignar sí). No consta la anulación en esta lectura: SIN VERIFICAR, aunque el mensaje del commit
y el diseño la declaran.

## TASK-GEN-0060 — CLOSED
Almacenamiento jsonb de `translate=True`: `TranslatedChar` (src/orm/fields_textual.py:888), lookups y orden por
idioma (:766-830), commits febd56b3 y ef86377b. Pruebas: tests/unit/orm/test_translated_char.py (14 casos) y
test_translated_ordering.py (4). Declarado sin consumidor: términos traducibles (`translate` invocable,
fields_textual.py:750-752). SIN VERIFICAR: si `Text`/`Html` con `translate=True` usan el mismo almacenamiento;
la importación/exportación por idioma es TASK-GEN-0062 (otra tarea).

## TASK-GEN-0391 — UNIT
`IrActionsServer.model_name` sigue `Char` (src/addons/base/models/ir_actions.py:1118) y varias secciones apuntan a
esta TASK como la que cablea `model_id`: `_warning_depends` (:1470-1485) y `warning` (:1590-1597) y el commit
027eb0a5 la nombra como la razón de un `depends` recortado. `ir.rule.model_id` ya es FK (ir_rule.py:202-208).
Fuente: `model_id` required, cascade (`odoo19c: odoo/addons/base/models/ir_actions.py:635-638`),
`_warning_depends` (:746-760) y `_compute_warning` (:804-805). Candidato:
`candidate-base-ir-actions-server-model-id-0391.jsonl`. SIN VERIFICAR: cuáles son "las tres tablas" del título
(`ir.filters.model_id` e `ir.attachment.res_model` también son Char: ir_filters.py:136, ir_attachment.py:112) y el
número de migración libre (última vista: 0128).

## TASK-GEN-0633 — BLOCKED
"Triar los 64 rojos de `tests/unit/orm` que TASK-API-0412 volvió alcanzables". Triar es ejecutar la suite y
atribuir cada rojo; no se puede ahora (gate PostgreSQL en curso). Además tiene dueño `codex-module-lifecycle`
(docs: progreso/bitacora-continuidad-...:173-180) y la cifra quedó vieja (63 restantes en H-API-1110;
commits posteriores tocaron `tests/unit/orm`). Condición de cierre: liberar el reclamo y ejecutar
`uv run pytest tests/unit/orm -q --reuse-db` para obtener la lista vigente; ahí cada rojo se clasifica contra
TASK-API-0413/0414/0417/0418/0419/0420/0422 (H-API-1110, "Ciega a").
