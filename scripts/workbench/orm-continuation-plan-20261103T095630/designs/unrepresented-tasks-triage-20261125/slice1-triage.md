# Triage de TASK sin unidad de plan: slice1

Raíz del puerto: `/home/user/kaupamex-api` (HEAD `91df3df0`, rama `feature/vm-x2hokp-orm-root`).
Referencia: `odoo19c` = `/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0`.
Confirmado: ninguno de los 15 ids aparece en `plan.jsonl` ni en `candidates/` (grep sin resultados).

| TASK | veredicto | razón | evidencia |
|---|---|---|---|
| TASK-API-0092 | BLOCKED | decisión de producto (retirar o conservar `seed_l0_chart`) y arista a 0091 pendiente; la parte ORM ya está en `chart.template` | chart_template.py:1090,1137,1255; hallazgo-H-API-348:245-252 |
| TASK-API-0174 | CLOSED | `_depth` con pila explícita y prueba de ciclo/cadena profunda | src/modules/module_graph.py:222-262; tests/unit/modules/test_module_graph_depth_limits.py:29,40,48 |
| TASK-API-0240 | NOT-ORM | gate de tooling (prosa/bloques vs alias de raíz) | analisis-contrato-de-basemodel-trae-o-construye.rst:119-121; scripts/reference_roots.py:58 |
| TASK-API-0269 | CLOSED | poda de addons no instalables y dependientes antes de poblar apps | src/config/settings/base.py:109-111; tests/unit/config/test_local_apps_installability.py:17,28,40,51,63 |
| TASK-API-0379 | BLOCKED | la siembra de `base.public_user` está hecha; falta sustituir el actor anónimo en la capa HTTP (decisión de seguridad) | src/addons/base/data/res_users_data.py:68; hallazgo-H-API-774:78-90; ir_http.py:99-103 |
| TASK-API-0401 | UNIT | la guarda ya está en `FieldDescriptor.__get__` pero no hay prueba que fije el acceso llano | src/orm/fields.py:1691-1703; odoo19c fields.py:1653-1661 |
| TASK-API-0407 | NOT-ORM | resolutor de raíz por marcador para `parents[N]` en pruebas de scripts | hallazgo-H-API-1096:51-60 |
| TASK-API-0411 | UNIT | aserción `unknown comodel_name` sin portar como system check | odoo19c fields_relational.py:92-94; hallazgo-H-API-1099 (sección «no cierra») |
| TASK-API-0420 | CLOSED | default de `Json` copiado por registro con `partial(deepcopy, default)` y siete pruebas | src/orm/fields_misc.py:62; tests/unit/orm/test_json_defaults.py:25-77 |
| TASK-API-0429 | UNIT | umbrella del porte de `test_orm`: 103 de 157 modelos y 13 de 23 archivos de prueba ausentes; se propone un primer tramo | tests/integration/test_orm; odoo19c odoo/addons/test_orm/models/ |
| TASK-API-0490 | NOT-ORM | filas `src/tools/pdf` del censo; adaptadores de `pypdf`, y esos archivos ya no existen | hallazgo-H-API-1148:62-64; src/tools/pdf/__init__.py:1-20 |
| TASK-API-0511 | CLOSED | `write` anuncia los calculados que protege; prueba unitaria y de integración | src/orm/models.py:3138; tests/unit/orm/test_write_announces_computed.py:51-71 |
| TASK-GEN-0058 | UNIT | faltan `is_initialized` e `initialize` en `src/modules/db.py` (4 de 6 símbolos portados) | odoo19c modules/db.py:20-124; src/modules/db.py:1-14,124 |
| TASK-GEN-0356 | UNIT | `get_installed` portado; `share` sigue como `property`, no como campo almacenado | res_lang.py:221; res_users.py:1844; odoo19c res_users.py:234,460 |
| TASK-GEN-0559 | CLOSED | `apply_except_missing` portado con desmarcado de ausentes y pruebas | src/orm/fields.py:5510-5539; tests/unit/orm/test_native_pending_recompute.py:87,117,219 |

Candidatos escritos: 0401, 0411, 0429 (primer tramo), GEN-0058, GEN-0356.

---

## TASK-API-0092: BLOCKED
Título del tablero: «Reconciliar seed_l0_chart con chart.template» (tablero-de-tareas.rst:994-998). H-API-348 deja dos mecanismos para el mismo trabajo (hallazgo-H-API-348:234-252). La mitad de diarios que bloqueaba ya se portó: `chart_template.py:1090` (`_setup_utility_bank_accounts`), `:1137` (`_create_outstanding_accounts`) y `:1255` (`get_account_journal`). `seed_l0_chart` ya escribe por `company_ids` (seed_l0_chart.py:63-78). Lo que queda es elegir: portar la creación de diarios y retirar el comando, o conservarlo declarando por qué L0 no usa plantilla. Eso es del operador L0, no del ORM. Además la bitácora registra la dependencia de 0091 pendiente (bitacora-recuperacion-del-control-y-admision-contractual.rst:16-19). Condición de cierre: decisión del ejecutor sobre el plan del operador L0 y cierre de 0091.

## TASK-API-0174: CLOSED
Commit `c58010a1` (ancestro de HEAD): `ModuleGraph._depth` usa marcos DFS explícitos (module_graph.py:222-262) y conserva `ModuleGraphCycle` con la ruta. Pruebas: ciclo largo, cadena acíclica profunda y limpieza del `path` del llamador (test_module_graph_depth_limits.py:29,40,48). La bitácora aclara que no cierra la TASK amplia ni el cargador completo (bitacora-profundidad-de-grafo-sin-limite-recursivo.rst:49-51); la obligación del título (RecursionError ante ciclo) sí está cubierta. SIN VERIFICAR: ejecución de la prueba (prohibido en este pase).

## TASK-API-0240: NOT-ORM
Su criterio histórico mide prosa y bloques de código contra la raíz que declara el alias (analisis-contrato-de-basemodel-trae-o-construye.rst:119-121). Es un gate de tooling sobre `scripts/reference_roots.py` y los artefactos; no corresponde a una obligación del ORM de Odoo 19.

## TASK-API-0269: CLOSED
H-API-654: `installable: False` no surtía efecto. Ahora `base.py:109-111` poda con `graph._remove(name)` los no instalables y sus dependientes antes de poblar `LOCAL_APPS`; cinco pruebas cubren poda, dependientes, ciclo en componente deshabilitado, ciclo en componente activo y compatibilidad (test_local_apps_installability.py:17-63). El hash `5744db36` que cita la bitácora no existe en este clon (git cat-file falla), pero el código está en HEAD. Límite declarado por la propia bitácora: no acredita composición del Registry por base (bitacora-catalogos-fisicos-y-reconciliacion-por-archivo.rst:49-51).

## TASK-API-0379: BLOCKED
H-API-774: `AllowAny` deja `AnonymousUser`, no un actor. La siembra de `base.public_partner`/`base.public_user` ya existe (res_users_data.py:68; migración 0113; test_public_user_seed.py). Falta la sustitución del actor en la capa HTTP (`_auth_method_public`, odoo19c ir_http.py:265-269), y ir_http.py:99-103 declara que el vocabulario se conserva pero no la implementación, porque montar un segundo camino de autenticación junto a ADR-018/DEC-11 no se hace de rebote. La bitácora y H-API-1120 exigen no introducir identidad de seguridad incidentalmente (tareas-completar-raiz-orm.rst:1268-1271, 1295). Condición de cierre: decisión del ejecutor sobre una clase de autenticación DRF que mapee el anónimo a `base.public_user`.

## TASK-API-0401: UNIT
H-API-1092 pedía extender la guarda de tamaño al acceso llano `rs.label`. En HEAD `FieldDescriptor.__get__` ya la implementa tras la terna de TASK-API-0402 (fields.py:1691-1703), y `_install_field_descriptor` instala descriptor de datos en todo campo (fields.py:2393-2399). Quedan dos pendientes verificables: una prueba que fije el acceso llano con el valor en `__dict__` (no la encontré: grep de `Expected singleton` solo da test_base_model_recordset.py:222,228, test_utils_record_adaptation.py y test_fields_relational_update_inverse.py:139) y comprobar que el docstring ya no enumera tres ramas (fields.py:1599-1612 no lo hace). Unidad pequeña, solo pruebas. SIN VERIFICAR: la afirmación de que ninguna otra suite lo cubre (contratos por trazas en tests/unit/orm/test_contract_model_record_reference.py:54-66 miden `can_return`, no el acceso llano).

## TASK-API-0407: NOT-ORM
H-API-1096: `parents[N]` equivocado en `tests/unit/scripts/test_check_identifier_language_stub.py:23`; el resolutor por marcador y su gate son tooling de pruebas (hallazgo-H-API-1096:51-60). No hay símbolo de Odoo 19.

## TASK-API-0411: UNIT
La fuente afirma `comodel_name in model.pool` en `setup_nonrelated` (odoo19c fields_relational.py:92-94). H-API-1099 resolvió el nombre punteado con centinelas `orm.<name>` pero dejó la aserción sin portar: un `_name` mal escrito queda colgado en `_pending_operations` y solo se ve mirando ese registro. En el puerto no hay "unknown comodel" (rg sin resultados en src/orm). Django ya emite `fields.E300/E307` para referencias perezosas (src/orm/checks.py:7-12) pero con el nombre del centinela. La unidad: un check que nombre campo y `comodel_name` original, registrado en `orm/checks.py`. Hay que medir primero si el setup de pytest-django ejecuta checks (lo pide el propio hallazgo) y si E300 ya cubre el caso. Alcance acotado: `One2many` queda en TASK-API-0410.

## TASK-API-0420: CLOSED
La fuente copia el default por registro; aquí `Json.__init__` envuelve el literal con `partial(deepcopy, default)` (fields_misc.py:62), lo que evita `fields.E010`. Siete casos: defaults anidados independientes, checks, serialización de migración, deconstruct/clone, callable/None/escalares, control negativo de Django crudo y metadatos (test_json_defaults.py:25-77). Commit `d1ec70f2` para la copia en lectura. El texto de bitácora indica que la aceptación final queda separada; el código y las pruebas existen.

## TASK-API-0429: UNIT (umbrella, tramo propuesto)
Estado `in_progress`. Medido con `_name`: referencia 157 modelos en `models/test_orm.py`, `test_performance.py` y `test_unity_read.py`; puerto 55 (`src/addons/test_orm/models/test_orm.py`), 103 ausentes por nombre (un extra propio: `test_orm.related_inherits_two`). Pruebas: la referencia trae 23 archivos `test_*.py`, el puerto no tiene 13 de ellos (`test_fields`, `test_indexed_translation`, `test_onchange`, `test_performance`, `test_properties`, `test_qweb_float`, `test_related_translation`, `test_schema`, `test_timeit`, `test_ui`, `test_unity_read`, `test_views`, `test_web_save`) en `tests/integration/test_orm`. El bloqueo de H-API-1124 (Many2many `relation, column1, column2`) ya está resuelto (`Many2manyField`, commits `2460b4e`, `486dca4`). Es demasiado grande para una unidad; se escribe un primer tramo acotado, `test_unity_read` (5 modelos, 45 casos, depende de `web_read` ya portado en addons/web/models/models.py:525). SIN VERIFICAR: cuántos de los 103 modelos faltantes son realmente portables (algunos dependen de vistas/UI) y el esquema de migración 0050.

## TASK-API-0490: NOT-ORM
Sin fila en el tablero; solo H-API-1148 la nombra como dueña de 8 filas `unresolved/not_verified` de `src/tools/pdf` (hallazgo-H-API-1148:62-64). Esas filas son adaptadores de `pypdf` (`_pypdf.py`, `_pypdf2_1.py`, `signature.py`), y esos archivos ya no están en el puerto (`git ls-files src/tools/pdf` no los lista); el motor PDF propio se declara en src/tools/pdf/__init__.py:1-20. `odoo/tools/pdf` no es ORM. El censo está desactualizado respecto de HEAD.

## TASK-API-0511: CLOSED
H-API-1209: `write` protegía los calculados que escribe y no llamaba a `modified()`. Commit `b68bff48` anuncia exactamente los silenciados, antes (relacionales) y después del guardado (models.py:3138-3150); commit `8f4cd889` añade el modelo de cómputo compartido de `test_orm`. Pruebas: `tests/unit/orm/test_write_announces_computed.py:51,58,64,71` y `tests/integration/test_orm/test_shared_compute.py`. Referencia: odoo19c models.py:4440-4484 (según el hallazgo, SIN VERIFICAR contra el archivo).

## TASK-GEN-0058: UNIT
`odoo19c: odoo/modules/db.py` declara 6 símbolos (db.py:20,29,127,162,168,192). El puerto tiene 4: `create_categories`, `FunctionStatus`, `has_unaccent`, `has_trigram` (src/modules/db.py:51,124,132,164). Faltan `is_initialized` (:20-26) e `initialize` (:29-124); el docstring lo admite (db.py:9-11). El consumidor en la fuente es loading.py:371-376. Aquí "initialize" es `migrate` (src/service/db.py:375) más `update_module_list`, así que la unidad es portar `is_initialized` y reconciliar `initialize` con esos dos mecanismos, declarando qué se sustituye (base_data.sql por migraciones). SIN VERIFICAR: si `update_module_list` ya cubre el cierre recursivo de auto_install (ir_module.py:390,403 sugiere que parte sí).

## TASK-GEN-0356: UNIT
`get_installed` de `ResLang` está portado (res_lang.py:221-226; tests/unit/base/test_res_lang_data.py). `share`: la fuente lo declara como `Boolean(compute='_compute_share', compute_sudo=True, store=True)` (odoo19c res_users.py:234) y calcula con `all_group_ids` (:459-464). El puerto lo deja como `property` (res_users.py:1844) bajo "divergencia de mecanismo" (res_users.py:563-567) y res_partner.py:2570 lo marca como pendiente. Sin campo almacenado no se puede consultar ni declarar `depends('user_ids.share')` (res_partner.py:1699, 2506). Unidad acotada: campo, compute, migración y restitución de los depends.

## TASK-GEN-0559: CLOSED
La fuente define `apply_except_missing` dentro de `Field.recompute` (odoo19c fields.py:1858-1875) y desmarca el cómputo de las filas ausentes. El puerto lo reproduce en `_recompute_native_recordset` (fields.py:5510-5539), incluido un único reintento con `exists()` y `remove_to_compute` de cada campo de `field_computed`. Pruebas: lote con ausentes (test_native_pending_recompute.py:87), reintento único ante `MissingError` persistente (:117), todos los ids ausentes retirados de cada campo calculado (:219). La bitácora deja pendiente la desaparición durante el cómputo (bitacora-as-is-y-recalculo-ausentes.rst:29-30): SIN VERIFICAR si el caso :117 lo cubre por completo.
