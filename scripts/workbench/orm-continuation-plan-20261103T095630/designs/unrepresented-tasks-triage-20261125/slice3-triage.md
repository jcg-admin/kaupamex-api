# Triaje slice3 — 15 TASK sin unidad en el plan

Plan: `scripts/workbench/orm-continuation-plan-20261103T095630/` (HEAD api `91df3df0`). Ninguna de las 15 aparece en `plan.jsonl` ni en `candidates/` como `taskId` (solo en `outputs/plan_coverage.json`, lista `unrepresented`).

| TASK | veredicto | razón | evidencia |
|---|---|---|---|
| TASK-API-0152 | CLOSED | La subclase consumidora de ResConfigSettings existe (el enunciado era falso) | addons/base_setup/models/res_config_settings.py:528; hallazgo-H-DOCS-188:21 |
| TASK-API-0217 | NOT-ORM | Gate estático de lint para código portado; Odoo no tiene análogo | hallazgo-H-API-617 (Registrado como #384); scripts/check_fk_naming.py |
| TASK-API-0265 | CLOSED | Registro de módulos sembrado (94 de 94) y pantalla servida por HTTP | tests/unit/base/test_update_module_list_roots.py:34-71; src/addons/base/controllers/admin_urls.py:26 |
| TASK-API-0283 | CLOSED | field_description ya es translate=True y el jsonb existe | src/addons/base/models/ir_model.py:930-931; tests/unit/orm/test_field_description_translation.py |
| TASK-API-0383 | NOT-ORM | DEC-AISL-05 es decisión de arquitectura de kaupamex, ya implementada; falta aceptación del ejecutor | src/orm/routers.py:178-187 |
| TASK-API-0404 | UNIT | La guarda `:289` no ve la etiqueta de Django; ya existe la vía diferida para cerrarlo | src/orm/fields_relational.py:1286-1302,1341-1350 |
| TASK-API-0409 | NOT-ORM | Sondas de workbench con `parents[N]`; es tooling, no obligación de la fuente | hallazgo-H-API-1096:76-81 |
| TASK-API-0414 | CLOSED | Superada: la clase NonStored se retiró y el campo sin columna es un models.Field | src/orm/fields_nonstored.py:7-13; commit f9b6bed9 |
| TASK-API-0424 | CLOSED | El aviso de campo no buscable es fiel a la fuente; cerrada sin código | hallazgo-H-API-1110:239-266; src/orm/fields.py:4600-4608; odoo19c: odoo/orm/fields.py:840-847 |
| TASK-API-0480 | UNIT | Quedan lecturas `<campo>_id.<attr>` sobre modelos que declaran el campo sin `_id` | addons/account_edi_ubl_cii/models/account_edi_xml_ubl_20.py:91,374 |
| TASK-API-0493 | CLOSED | Cubierta por la unidad ptav-complete-0122 (aceptada) | addons/product/models/product_template_attribute_value.py:55,141,199,231; plan.jsonl:363 |
| TASK-DOCS-0111 | NOT-ORM | Corrección del tablero (#278/#99); trabajo de docs | hallazgo-H-DOCS-188:8-20 |
| TASK-GEN-0062 | BLOCKED | Motor `.po` (odoo/tools/translate.py) sin diseño ni decisión de alcance | src/tools/translate.py:1-40; tools/translate.py:709-1050,1519 |
| TASK-GEN-0453 | UNIT | De los tres transitorios, IrDemo sigue sin medir; ResConfig espera decisión | src/addons/base/models/ir_demo.py:53-62; designs/resconfig-transient.md |
| TASK-GEN-0634 | UNIT | Siete @property de ResCompany que la fuente declara related | src/addons/base/models/res_company.py:512-562 |

## TASK-API-0152 — CLOSED
Título del tablero: «ResConfigSettings abstracto sin subclase consumidora» (ordinal 278). H-DOCS-188 midió que sí hay subclase real. Hoy `class SiteConfigSettings(ResConfigSettings)` está en `addons/base_setup/models/res_config_settings.py:528`, con pruebas en `tests/integration/base_setup/test_company_delete_with_a_tableless_form.py`. La bitácora `bitacora-relaciones-virtuales-y-entorno-de-registros.rst:25-31` ya preservó la identidad sin reabrirla. Limitación: no se midió herencia indirecta (la métrica de H-DOCS-188 es ciega a ella).

## TASK-API-0217 — NOT-ORM
Es la tarea #384 de H-API-617: un gate para tres formas de traducción del recordset (FK obligatoria `is None`, Many2many como gestor, `getattr` sobre `get_current_company()`). Es verificación estática del código portado; la fuente no tiene un equivalente en `odoo/orm`. Existen gates vecinos en `scripts/` (`check_fk_naming.py`, `check_model_name_lookup.py`). El análisis `analisis-contrato-de-basemodel-trae-o-construye.rst:2299` la declara «sin seleccionar por mera ausencia nominal». Si el ejecutor la quiere, es unidad de tooling, no de ORM.

## TASK-API-0265 — CLOSED
Título: «Sembrar el registro de módulos para que la pantalla de aplicaciones sea visible» (ordinal 449). H-API-649 lo resolvió (`update_module_list` registra 94 de 94 addons). Prueba: `tests/unit/base/test_update_module_list_roots.py` (control positivo en :34). Servicio HTTP: `/api/v2/admin/technical-modules/` (`src/addons/base/controllers/admin_urls.py:26`, prueba `tests/integration/base/test_module_catalogue_api.py`). Lo que H-API-649 dejó abierto, el árbol de categorías, es otra tarea (TASK-API-0267, ordinal 452) y el puerto ya llama `create_categories` (`src/addons/base/management/commands/update_module_list.py:92`). El commit `5a84f1ff` citado en la bitácora no existe en este clon: SIN VERIFICAR su hash, pero el código y la prueba sí.

## TASK-API-0283 — CLOSED
`ir.model.fields.field_description` con `translate=True` (odoo19c: odoo/addons/base/models/ir_model.py:525). Port: `src/addons/base/models/ir_model.py:930-931` en HEAD, commit `78520aae` (ancestro de HEAD), prueba `tests/unit/orm/test_field_description_translation.py`. La dependencia de aceptación con almacenamiento (análisis :2229) se levantó: `febd56b3` guarda los 14 campos translate como jsonb por idioma (TASK-GEN-0060). Fuera de alcance: `help` también es translate en la fuente (ir_model.py:526) y no se midió aquí; SIN VERIFICAR.

## TASK-API-0383 — NOT-ORM
DEC-AISL-05 («cada base de empresa es una instalación completa») es una decisión de arquitectura de kaupamex, no una obligación de odoo19c (allá solo hay un registro por base). Está implementada: `allow_migrate` migra el dominio a `default` y a cada `company_<N>_db` (`src/orm/routers.py:178-187`). Lo que queda según `decisiones-implementar-aislamiento-multi-db-per-company.rst:127-131,167` es revisión, aceptación e integración por el ejecutor, y los fixtures de aislamiento, que ya tienen unidades propias (`multidb-gate-clone`, `multidb-run-intent-0496`, `orm-init-alias-propagation-0515`).

## TASK-API-0404 — UNIT
`ondelete='restrict'` hacia un modelo de `IR_MODELS` se rechaza en la fuente (odoo19c: odoo/orm/fields_relational.py:289-295). El puerto compara en `_apply_ondelete` la cadena o `name_of(clase)` (`src/orm/fields_relational.py:1286-1302`); una etiqueta de Django (`'base.IrModel'`) no se compara con nada. Hoy hay 0 declaraciones así en el árbol (grep medido), por eso es hardening, no bug vivo. Con TASK-API-0405 ya existe el mecanismo diferido (`lazy_related_operation`, :1341-1350) para resolver la etiqueta cuando el modelo carga, y `model_by_key` (`src/orm/registry.py:528`) acepta ambos vocabularios. Candidato: `candidate-orm-many2one-ondelete-django-label-0404.jsonl`.

## TASK-API-0409 — NOT-ORM
Barrer cinco bancos de `scripts/workbench/` que resuelven la raíz por `parents[N]` (H-API-1096:76-81, sucesor del `parents[3]` de un test). Son sondas de medición del propio proyecto, sin contraparte en odoo19c. La TASK hermana TASK-API-0407 (resolutor por marcador) es el mecanismo. No es ORM.

## TASK-API-0414 — CLOSED
Premisa: «un NonStored no tiene atributo `editable`». La clase se retiró en `f9b6bed9` (TASK-API-0418): hoy el campo sin columna es un `models.Field` con `store=False` contribuido con `private_only=True` (`src/orm/fields_nonstored.py:7-13`), que trae `editable` de Django; `apply_source_defaults` incluso lo fija (:215-224). `Field.is_editable` de la fuente (odoo19c: odoo/orm/fields.py:972) está portado en `src/orm/fields.py:3251-3263`. SIN VERIFICAR: una prueba que ejerza `editable` sobre un campo `store=False` en particular; el cierre se apoya en que la clase ya no existe.

## TASK-API-0424 — CLOSED
El campo sin columna de una cadena related «no es buscable» emite el aviso `should be searchable`. La fuente lo emite con la misma condición y texto (odoo19c: odoo/orm/fields.py:840-847) y declara `res.company.country_id` sin `search` (res_company.py:79), igual que el puerto. Port del aviso: `src/orm/fields.py:4600-4608`. H-API-1110:239-266 lo cerró sin código el 2026-09-14. Los `related` sí reciben `search` (`src/orm/fields_nonstored.py:297-304`). Ciega a: si la fuente suprime el aviso en ejecución por otra vía (declarado en el hallazgo). Ojo: el tablero sigue en `pending`; es desfase de registro, no de código.

## TASK-API-0480 — UNIT
H-API-1144: la familia `account_edi_ubl_cii` se portó con «la puerta está bloqueada, las habitaciones no»; quedan lecturas con la forma `<campo>_id.<atributo>`. Se midió el modelo receptor: `AccountMove` declara `partner`, `journal`, `currency` (account_move.py:143-157), `AccountMoveLine` declara `account` y `currency` (account_move_line.py:78,133) y `AccountPartialReconcile` declara `credit_move` (account_partial_reconcile.py:80). Por eso son sospechosas `account_edi_xml_ubl_20.py:91` (`invoice.partner_id.lang`), `:374` (`.partner_id.country_code`), `account_edi_ubl_pint.py:129` (`line.account_id`) y `:134` (`credit_move_id`). Matiz: `AccountMoveLine` sí declara `partner_id`, `journal_id`, `company_id` (:172,188,216), así que no todas fallan; el conteo por nombre no decide (el propio hallazgo lo dice). Si `BaseModel` resuelve alias `*_id` a registro está SIN VERIFICAR; la unidad debe medirlo primero. Candidato: `candidate-account-edi-ubl-source-names-0480.jsonl`.

## TASK-API-0493 — CLOSED
Sucesora de `a203cc69` (TASK-API-0482): «doce métodos, once campos y la restricción con nombre» de `product.template.attribute.value` (bitácora-reconciliacion:163-167). La unidad `ptav-complete-0122` (plan.jsonl:363; diseño `designs/ptav-complete.md:3-4` declara a 0493 como su origen) está aceptada (`continuation.jsonl:673`, commit `471db3b6`, código `036426ae`). Código verificado: `ptav_active` (product_template_attribute_value.py:55), `_attribute_value_unique` (:127), `_check_valid_values` (:141), `unlink` (:199), `_compute_display_name` (:231); prueba `tests/unit/product/test_ptav_complete.py` (7 casos). Lo que el diseño deja a otras unidades (`exclude_for`, `_create_variant_ids`) tiene unidad propia (`product-template-variant-generation-0122`).

## TASK-DOCS-0111 — NOT-ORM
«Corregir #278 y cerrar #99 — su propia evidencia las contradice» (H-DOCS-188). Es edición del tablero de tareas (docs). La bitácora `bitacora-relaciones-virtuales-y-entorno-de-registros.rst:25-31` declaró que se preservó su identidad sin reapertura. Sin ORM.

## TASK-GEN-0062 — BLOCKED
«Construir el motor de traducción: import/export de .po». Corresponde a `odoo/tools/translate.py` (PoFileReader :818, PoFileWriter :937, TranslationImporter :1519, trans_export :1047), no a `odoo/orm`. `src/tools/translate.py` (80 líneas) solo porta `_` con formato (docstring :1-40); esos símbolos figuran `absent` en `obligation_classification.tsv` bajo TASK-API-0486. Su bloqueo declarado, el almacenamiento jsonb (TASK-GEN-0060), ya se cumplió en código (`febd56b3`), pero el tablero lo sigue como `pending`. Falta: (a) decisión del ejecutor sobre si el motor `.po` entra en el alcance y cómo se mapea a `res.lang`/catálogos Django, (b) diseño previo (`designs/` no tiene uno para `.po`). Condición de cierre: decisión + diseño en `designs/`; luego se parte en unidades por lector, escritor e importador. Relacionada TASK-API-0375 (catálogo `.po` por addon).

## TASK-GEN-0453 — UNIT (parcial)
«Veredicto a los tres transitorios que declaran managed=False»: `IrDemo`, `BaseEnableProfilingWizard`, `ResConfig` (`src/orm/models_transient.py:24`). Estado: `BaseEnableProfilingWizard` ya tiene tabla (ir_profile.py:588-650, migración 0086); `ResConfig` es una decisión de arquitectura pendiente del ejecutor (`designs/resconfig-transient.md`, opciones A/B); `IrDemo` sigue `abstract`+`managed=False` (ir_demo.py:61-62) aunque la fuente es transitorio con tabla (odoo19c: odoo/addons/base/models/ir_demo.py:7-19) y un abstracto no admite `create({})`. Candidato para IrDemo: `candidate-orm-ir-demo-transient-table-0453.jsonl`. `ResConfig` queda BLOCKED por decisión. Nota: el ordinal 201 de esta TASK colisiona con otra tarea completada según la bitácora; se usa solo el id durable.

## TASK-GEN-0634 — UNIT
La referencia declara `name`, `logo`, `email`, `phone`, `website`, `vat`, `company_registry` como `related='partner_id.*'` (odoo19c: odoo/addons/base/models/res_company.py:48,62,81-85), con `store=True` en name, email y phone, más `company_registry_placeholder` (:86). El puerto aún usa @property (name, email, phone con setter; website, vat, logo, billing_name de solo lectura; res_company.py:512-562); `company_registry` y su placeholder no existen (solo se mencionan en el docstring :27). `billing_name` no está en la fuente (grep 0). Una cadena `related` que los recorra muere (H-API-1111:166-170). Los avisos de H-API-1110 siguen. Dependencias de orden por el mismo archivo: `base-company-init-paperformat-0515` y `orm-init-alias-propagation-0515`. Candidato: `candidate-orm-res-company-related-fields-0634.jsonl`. La migración pide numeración (hoy la última es 0128); el id `0129` es provisional.
