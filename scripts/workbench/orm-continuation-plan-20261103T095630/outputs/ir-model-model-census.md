<!-- Procedencia: subagente de investigación de sólo lectura (2026-11-23), nivel 3 de retención. Verificado de forma independiente por la sesión: registry.py:2446-2447 filtra ir.model por m._name (hoy latente porque la columna guarda etiquetas), name_of/model_by_name/model_by_key en registry.py:512-530, y la fila de stock.model_stock_picking con model=stock.StockPicking (sonda pytest del 2026-11-23). El resto de cifras no se ha re-medido. -->

# Censo: `ir.model.model` guarda la etiqueta de Django; la fuente guarda `_name`

Alcance: lectura sola sobre `/home/user/kaupamex-api`. Fuente: `odoo19c: odoo/addons/base/models/ir_model.py:428` (`'model': model._name`).
Todas las rutas `src/...` son relativas a `/home/user/kaupamex-api`.

## 0. Hechos de partida (medidos)

- Columna: `IrModel.model`, `Char(255)`, único (`ir_model_obj_name_uniq`), `_order='model'` — `src/addons/base/models/ir_model.py:373-405`.
- Traducción etiqueta↔`_name` ya existente en `src/orm/registry.py`:
  `name_of(model)` (`:512`, lee `model.__dict__['_name']`), `model_by_name(name)` (`:521`), `model_by_key(key)` (`:527`, acepta **ambas** formas), `MODELS_BY_NAME`, `resolve_model_key` (`:565`). `IrModelAccess._model_label` (`ir_model.py:2672`) traduce `_name` → etiqueta (la dirección contraria a la que se quiere).
- Modelos (runtime, `config.settings.testing`, `django.setup()` sin tocar la base; script `/tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/rt_count.py`):
  `apps.get_models(include_auto_created=True)` = **550**; con `_name` propio **289**; sin `_name` **261**, de los cuales **96** son `auto_created` (tablas M2M) y **165** no (164 con `label` único listado en `scratchpad/unnamed_labels.txt`; la diferencia de 1 es un nombre de etiqueta repetido en el conteo por clase). `MODELS_BY_NAME` = 291, sin `_name` duplicado.
- Hay incoherencia **hoy** entre lectores: unos esperan etiqueta y otros `_name` (secciones 2 y 3). Es la señal de que el cambio también corrige defectos latentes.

## 1. ESCRITORES de `IrModel.model` / filas de `ir.model`

| # | Sitio | Valor que escribe | De dónde lo saca |
|---|---|---|---|
| W1 | `IrModel._reflect_models` — `ir_model.py:796-857` (`label = f'{app_label}.{object_name}'` en `:828`; `bulk_create(update_conflicts=True, unique_fields=['model'])` en `:850`) | etiqueta de Django | `model._meta.app_label` + `object_name`; **recorre `apps.get_models()` entero**, también los sin `_name` |
| W2 | `Registry._reflect_models` — `src/orm/registry.py:2425-2452` | delega en W1 (`ir_model._reflect_models(app_labels, module=…)`) | `app_labels` de las clases cargadas |
| W3 | `_seed` de ACL — `src/addons/base/security/ir_model_access.py:550` (`IrModel.objects.using(using).get_or_create(model=label, defaults={'name': …})`) | etiqueta | `_ACCESS` (`:167` ejemplos `'base.IrModel'`); lo ejecutan migraciones `0059_seed_base_security`, `0095_seed_attachment_acl`, `0096_rederive_base_acl`, `0122_seed_derived_acl` y las `seed()` del catálogo de tests |
| W4 | `IrModel.name_create` — `ir_model.py:633` | `x_<nombre>` (modelo manual) | ya es válido como `_name` |
| W5 | `IrModel._reflect_constraint*`/`_reflect_relation` leen (no escriben) — `:2340`, `:2538` | — | ver lectores |
| W6 | Migraciones `src/addons/base/migrations/` (129 archivos): **ninguna** escribe `ir_model` como dato; `0001_initial.py:967` sólo crea la tabla; `0073` sólo cambia `help_text`; `0105_irrule_model_id_global.py:19-26` **lee** `IrModel.model` (ver §3). | — | — |
| W7 | Pruebas: 56 sitios `IrModel.objects.get_or_create/create(model=…)` en `tests/` (p. ej. `tests/unit/base/test_reflect_field_params.py:26` etiqueta `'base.IrModel'`; `tests/unit/base/test_model_menu_create.py:25` `_name` `'res.partner'`) | mezcla | — |

Comando: `grep -rnE "IrModel\.objects|get_or_create\(model|bulk_create|_reflect_models" src addons tests --include=*.py`.
Un único escritor de producción real (W1) más una siembra (W3). `_update_model_xmlids` (`ir_model.py:859-891`) **lee** por etiqueta y deriva `model_<_name con _>` (`:886-888`): ya usa `_name` para el XML-ID y la etiqueta como clave de unión.

## 2. LECTORES de `IrModel.model`

Clasificación: (A) espera etiqueta de Django, (B) espera `_name`, (C) indiferente.

### 2.1 Dentro de `ir_model.py`
| Sitio | Qué hace | Clase |
|---|---|---|
| `:407` `__str__` | devuelve `self.model` | C |
| `:410-423` `django_model` (`self.model.split('.',1)` + `apps.get_model(app, name)`) | resuelve etiqueta → clase | **A** (rompe con `_name`: `res.partner` → app `res`) |
| `:461` `_inherited_models` (`filter(model__in=parent_labels)`, etiquetas del `mro`) | A |
| `:476` `view_ids` (`IrUiView.objects.filter(model=self.model)`) | une con `ir_ui_view.model` (Char propio) | A (cambia con la tabla del cruce, §4) |
| `:527-532` `_check_model_name` (`check_object_name`: minúsculas/dígitos/`_`/`.`) | **B**: una etiqueta como `stock.StockPicking` **no pasa**; `_name` sí | B |
| `:699-713` `delete`: `IrModelFields.objects.filter(relation=…)`, `IrCron…ir_actions_server__model_name=`, `IrModelData.objects.filter(model=…)` con `self.model` | une con 3 Char por valor | A (hoy) |
| `:719-733` `_get(name)`, `:736-748` `_get_id(name)` (`filter(model=name)`) | **B en la fuente**; hoy sólo acierta con etiqueta | ver §2.3 |
| `:841`, `:850` reflejo | W1 | — |
| `:887` `owned[row.model]._name` | indexa por etiqueta | A |
| `:1079-1080` `IrModelFields…IrModel._get(self.model)` | pasa `ir_model_fields.model` | A |
| `:1386`, `:1509`, `:1609`, `:1689`, `:1740` `model_row.model`/`self.model_id.model` → `IrModelFields.model`; `:1617` `model=self.relation` | copian el valor | A (propagan) |
| `:2340`, `:2538` `IrModel.objects.filter(model=label)` con `model_cls._meta.label` | A |
| `:2666`, `:2748`, `:2833`, `:2877` `model_id__model=cls._model_label(...)`/`values_list('model_id__model')` en `IrModelAccess` | **A** (centro del cuello: `label in _get_allowed_models(...)` en `:2788`) |
| `:2938` `_make_access_error`: `IrModel.objects.filter(model=model)`, `model` = etiqueta de `orm/models.py:413` | A |

### 2.2 Fuera de `ir_model.py` (src/addons/orm)
| Sitio | Qué espera | Clase |
|---|---|---|
| `src/orm/models.py:413,420` `Access.check(label,…)`, `Access._make_access_error(label…)` con `self.model._meta.label` | etiqueta | A |
| `src/orm/models.py:2627-2629` `IrModel.objects.filter(model=self._meta.label)` (`_model_description`) | etiqueta | A |
| `src/orm/models.py:3651-3652` `IrModel._get(_model_name(cls))`; `_model_name` (`:277-280`) = `_name` **o** `label_lower` | **B** (hoy no acierta con etiqueta cuando hay `_name`; cae al `_description`) | B |
| `src/orm/environments.py:2234-2237` `ir_model._get(model_name)` con `model._name or label_lower` | **B** (mismo desfase) | B |
| `src/orm/registry.py:2447-2452` `ir_model.objects.filter(model__in=[m._name for m in model_classes])` y luego `row.django_model` | **B** (contra una columna con etiquetas: no empareja nunca con modelos que tienen `_name`; tras el cambio **empezaría a ejecutar** `_reflect_fields`/`_reflect_inherits`/`selections`/`constraints` para esas filas) | B, con cambio de comportamiento |
| `src/addons/base/models/ir_actions.py:1383` `related='crud_model_id.model'`; `:1924`,`:1932`; `:2027-2030` (`IrModel.objects.filter(pk=…)` + `model_by_key(row.model)`); `:2306-2311` `_crud_model` (`apps.get_model(name)` con `crud_model_id.model` **o** `model_name`); `:2400` y `:2419-2439` (`IrModel.objects.filter(model=label/self.model_name/field_row.relation)`); `:1910` `_selection_target_model` (`(row.model, row.name)`) | etiqueta (`apps.get_model(name)` sólo admite etiqueta); `model_by_key` admite las dos | A mayoritario; `:2030` C |
| `src/addons/base/models/ir_actions_report.py:597` `IrModel._get(self.model)`; `:620-658` `_search_model_id` (`Domain('model','in', rows.values_list('model'))` sobre el Char `model` del reporte) | une `ir_actions_report.model` con `ir_model.model` | A (la misma convención que el reporte) |
| `src/addons/base/models/ir_rule.py:649` (`IrModel.objects.filter(model=model)` con etiqueta), `:819-823` | A |
| `src/addons/base/report/report_base_report_irmodulereference.py:88` (`pk__in`) | C |
| `addons/base_automation/models/base_automation.py:549`, `:554-556`, `:865`, `:932` (`self.model_id.model`, `IrModel.objects.filter(model=self.model_name)`); `addons/base_automation/models/signals.py:65-68` (`f'{app_label}.{sender.__name__}'`, declara "mismo formato que `IrModel.model`") | etiqueta | A (el despachador de señales compara contra la etiqueta) |
| `addons/web/models/ir_model.py` (`_is_valid_for_model_selector`: `cls.objects.get(model=model_name)`; `_display_name_for`: `filter(model__in=model_names)`; `display_name_for`) | lo que reciba del cliente; hoy espera etiqueta | A (contrato HTTP externo) |
| `addons/web/controllers/export.py:72-73` divergencia declarada: "`model` usa `app_label.ModelName`, no `dominio.punto`" | etiqueta | A |
| `addons/mail/models/mail_alias.py:171,200` (FK a `ir.model`, no lee `.model`) | C |
| `addons/account/demo/account_demo.py:164,171` `IrModelData.objects.filter(model='product.template')` | **B** contra la tabla `ir_model_data` (hoy etiqueta) | B (latente) |

### 2.3 Cifras
- Archivos de `src/`+`addons/` que importan o usan `IrModel`/`model_id.model`: ver comando abajo (22 archivos de `src/`+`addons/`, además de `ir_model.py`).
- Pruebas: **138** líneas de uso (no import) de `IrModel` en **49** archivos de `tests/`; los 56 sitios de creación se clasifican: etiquetas (`'base.IrModel'`, `ResDeviceLog._meta.label`, `'hr.HrEmployee'`, `'orders.Order'`) y nombres punteados (`'res.partner'`, `'res.groups'`, `'x_report_probe'`) — mezcla.
- Scripts: 0 lectores de producción (`scripts/**` sólo trae sondas de bancos `workbench`/`evidence` que importan `IrModelData`/`IrModel`; `scripts/gate_preflight.py:57` lee `ir_model_data`, no `ir_model`).
- SQL crudo: 0 consultas a `ir_model` fuera del ORM (grep `FROM ir_model\b|JOIN ir_model\b`); `ir_model_data` sí se escribe con SQL crudo (`ir_model.py:3284`, `:3386`).

Comandos: `grep -rnwE "IrModel" src addons scripts --include=*.py | grep -v "src/addons/base/models/ir_model.py"`; `grep -rnE "model_id\.model\b|model_id__model|crud_model_id\.model|IrModel\._get\(" src addons --include=*.py`.

## 3. `ir.rule.model_name` (`src/addons/base/models/ir_rule.py`)

- Columna: `Char(120)`, doc "Label del modelo, p.ej. 'sale.SaleOrder'" — `:189-194`; `model_id` es FK a `IrModel` (`:203`), nulable.
- Sincronía: `_sync_model_reference` (`:801-822`), llamada desde `save` (`:333`): gana el que cambió; `model_id` asignado → `model_name = model_id.model`; si no, `model_id = IrModel.objects.filter(model=self.model_name).first()`.
- Migración de datos: `0105_irrule_model_id_global.py:19-26` rellena `model_id` con `Subquery(IrModel.filter(model=OuterRef('model_name')))` — **ya ejecutada**; si `ir_model.model` cambia de valor sin reescribir `ir_rule.model_name` en el mismo paso, `model_id` quedaría `NULL` en la próxima ejecución del reflejo/`save`.
- Lectores de `model_name`:
  - `_get_rules(model_name…)` `:401-421` (`filter(model_name=model_name…)`), `_compute_domain` `:454-483`, `@ormcache('model_name',…)` — **A**: los llamadores pasan `queryset.model._meta.label` (`:549`, `:579`, `:531`, `:637`) y `src/orm/models.py:9083`.
  - `_check_domain` `:306-307` (`self.model_name.split('.',1)` + `apps.get_model`) — **A** (se rompe con `_name`).
  - `:504`, `:520` `apps.get_model(model_name)` — **A**.
  - `_check_model_name` `:269-278` (`self.model_name == self._name`) compara con `'ir.rule'` — **B** (hoy inerte: nunca igual a la etiqueta `base.IrRule`; tras el cambio por fin dispara).
  - `:637-649` `_make_access_error`: `IrModel.objects.filter(model=model)` — A.
- Siembras: `src/addons/base/security/base_security.py:33` (`_RULES = (('Company Setting multi-company','base.CompanySetting'),)`, `:36-44` crea `IrRule(model_name=…)`), `addons/sale/security/ir_rules.py:15` (`'sale.SaleOrder'`), `addons/sale_subscription/security/ir_rules.py` (2 archivos `ir_rules.py` en total). Las ejecutan migraciones `0059`, `sale/0007_seed_sale_security`, `sale_subscription/0002_seed_subscription_security`. Todas etiqueta.
- Fuente: `model_name` es `related='model_id.model'` — por tanto es `_name` en la fuente. La decisión sobre `ir.rule.model_name` es: o se queda como etiqueta (y `_sync_model_reference` traduce), o pasa a `_name` (y los lectores A de arriba cambian a `model_by_key`).

## 4. Otras columnas "modelo" y su cruce con `ir.model`

Qué guardan hoy (escritura medida):

| Columna | Qué guarda hoy | Cómo la escribe | Cruce con `ir_model.model` |
|---|---|---|---|
| `ir.model.fields.model` (`ir_model.py:911`) | etiqueta | `:1689`, `:1740`, `:1609` (copia `model_row.model`) | **sí** (`_get_ids(model_name)` `:1315`, `field_id__model` `:1915`, `delete` por `relation` `:699`) |
| `ir.model.fields.relation` (`:923`) | etiqueta (`f'{app_label}.{object_name}'`, `:1702`) | reflejo | **sí** (`delete` `:700`; `ir_actions.py:2434`) |
| `ir.model.data.model` (`:2980`) | etiqueta (`type(record)._meta.label`, `:3320`; SQL `:3386`) | `_update_xmlids` | **sí** (`IrModel.delete` `:713`, `:3541`, `:3553`); `account_demo.py:164` espera `_name` |
| `ir.model.constraint.model` / `ir.model.relation.model` | FK a `IrModel` (`:2263`, `:2490`) | `:2340`, `:2538` (por etiqueta) | por FK |
| `ir.model.access` | FK `model_id`; la clave es `model_id__model` | ACL sembrada W3 | **sí**, central |
| `ir.rule.model_name` | etiqueta | §3 | **sí** |
| `ir.actions.server.model_name` (`ir_actions.py:1118`) | etiqueta | formularios/siembras de acciones | **sí** (`crud_model_id`, `IrModel.delete` `:708-711`) |
| `ir.actions.report.model` (`ir_actions_report.py:448`) | etiqueta ("mismo criterio que ir_rule.model_name") | datos | **sí** (`_compute_model_id`, `_search_model_id`) |
| `ir.default.model` (`ir_default.py:127`) | etiqueta (`"sale.SaleOrder"`) | `set`/API | no cruza directamente; mismo vocabulario |
| `ir.ui.view.model` (`ir_ui_view.py:279`), `ir.actions.act_window.res_model` (`:522`), `ir.actions.client`/`todo` `res_model` (`:755`), `ir.actions.actions.binding_model_name` (`:304`), `ir.embedded.actions.parent_res_model` (`ir_embedded_actions.py:123`), `ir.attachment.res_model` (`ir_attachment.py:112`), `mail.followers/activity/activity_type/message/message_subtype/template` (`res_model`/`model`), `res.users.settings.embedded.action.res_model` (`addons/web/...:99`), `base_automation.model_name` (`:386`) | etiqueta (todas sus `help_text` ejemplifican `app.Model`) | — | `view_ids` (`:476`) y `base_automation` cruzan; el resto sólo comparten vocabulario |

Lo que ya existe para traducir: `name_of` (`registry.py:512`), `model_by_name` (`:521`), `model_by_key` (`:527`, consumido por `fields_relational.py:337,464,535` y `ir_actions.py:634,1749,1870,2030`). `IrModelAccess._model_label` (`ir_model.py:2672`) sólo traduce `_name` → etiqueta. No existe `label_to_name` (etiqueta → `_name`) más allá de `name_of(model_by_key(label))`. Para un modelo sin `_name` (§5) no hay valor `_name`.

## 5. Modelos sin `_name`

- Runtime (testing): **165** no auto-creados sin `_name` propio (más 96 `auto_created` M2M). Reparto por app (todas las clases sin `_name`, incluidos los M2M): base 34, stock 21, mail 13, test_orm 12, product 12, account 11, authz 8, website 7, payment 7, delivery 7, mrp 7, hr 6, hr_recruitment 6, …
- Heurística de contraparte (camel → punteado contra `grep -rhoE "_name = '…'"` de `odoo19c/addons` y `odoo/`, 1513 nombres): **40** tienen contraparte con ese nombre (p. ej. `base.IrActionsActions`, `base.IrFilters`, `base.IrLogging`, `base.ResCountryGroup`, `mail.MailMessage`, `mail.MailTemplate`, `digest.DigestDigest`) y **125** no la tienen por nombre derivado (modelos propios del L0 como `authz.*`, `delivery.*`, `loyalty.*`, `payment.*`, y apps de Django: `auth.Group`, `auth.Permission`, `admin.LogEntry`, `contenttypes.ContentType`, `token_blacklist.*`). Archivos: `scratchpad/unnamed_hit.txt`, `scratchpad/unnamed_miss.txt`.
- Valor que debe guardar `model` para ellos:
  - con contraparte en la fuente (40, ya sin `_name` por porte incompleto): el `_name` de la fuente — **requiere declarar `_name` en la clase** (regla `atributos-de-clase-de-modelo.md`: se portan todos los atributos declarados);
  - propios del L0 (la fuente no tiene contraparte): conservar la **etiqueta** (`app.Model`) como valor, que cumple `check_object_name` sólo si se normaliza a minúsculas (`label_lower`: `delivery.shippingzone`) — **decisión del ejecutor**: o `label` verbatim (viola `_check_model_name`) o `label_lower` (nombre derivable, único, resoluble con `apps.get_model` porque Django es insensible a mayúsculas en `get_model(app, name)`). El gate `_check_model_name` (`:519-532`) sólo corre en `clean()`, no en el reflejo.
  - apps de Django (`auth`, `admin`, `contenttypes`, `token_blacklist`): quedan con `label_lower` o dejan de reflejarse (W1 hoy las refleja a todas).
  - M2M `auto_created`: sin contraparte; `label_lower`.

## 6. Partición propuesta (cada unidad cierra con verde propio)

**U0 — traducción central (sin cambiar datos).** Añadir en `orm.registry` una función única `reflected_name(model)` = `name_of(model)` o `model._meta.label_lower`, y su inversa tolerante `model_by_key` ya existente. Razón: es el contrato que usan todas las unidades siguientes; sin ella cada lector reimplementaría la regla (sub-patrón A de `metrica-decide-la-conclusion.md`). Cubierta por: pruebas de `registry` (`tests/unit/orm/test_registry_*`), `tests/unit/orm/test_extension_tardia_por_nombre.py` (9 usos).

**U1 — lectores tipo A pasan a resolver por `model_by_key` (aún con etiquetas en la tabla).** Cambiar `IrModel.django_model` (`:410-423`), `_check_domain`/`:504`/`:520` de `ir_rule.py`, `ir_actions.py:2306-2311` (`apps.get_model(name)`), `_inherited_models` (`:461`) y `IrModelAccess._model_label` para que acepten ambas formas y devuelvan la forma que **la tabla guarde** (parámetro único). Razón: es reversible y no toca datos; deja el sistema funcionando con etiquetas **y** con `_name`. Pruebas existentes: `tests/integration/base/test_ir_model_access_check.py`, `test_ir_model_access_groups.py`, `tests/unit/base/test_ir_rule_model_id.py`, `test_ir_rule_access_error.py`, `tests/unit/base/test_ir_actions_server_*`, `tests/unit/orm/test_related_traversal_access.py`, `tests/integration/test_orm/test_basemodel_access_against_rules.py`.

**U2 — escritura: reflejo + siembra escriben `_name`, y migración de datos reescribe filas.** (a) `_reflect_models` (`:828`) toma `reflected_name`; `expected`/`classes` pasan a indexarse por ese valor (`:841`, `:887`, `_update_model_xmlids`); `_seed` de ACL (`ir_model_access.py:550`) igual. (b) Migración `base` que, en una transacción, reescribe `ir_model.model` y **las columnas que cruzan por valor**: `ir_model_fields.model` y `.relation`, `ir_model_data.model`, `ir_rule.model_name`, `ir_actions_server.model_name`, `ir_actions_report.model`, `ir_ui_view.model` (esas tres últimas sólo si el criterio de §4 las incluye). Razón del corte conjunto: `ir_model.model` es clave de unión por valor para esas seis tablas (sin FK); reescribir una sin las otras deja filas huérfanas silenciosas (`IrModel.delete` `:699-713` no las encontraría; `_get_ids` `:1315` devolvería `{}`). `unique_fields=['model']` en `bulk_create` (`:850`) exige que la reescritura sea determinista y sin colisiones: precondición medible (`label_lower` y `_name` únicos). Cubierta por: `tests/unit/base/test_reflect_models_xmlids.py`, `test_reflect_model_params_ordering.py`, `test_reflect_field_params.py`, `tests/integration/base/test_ir_model_reflect_write_path.py`, `test_ir_model_relation_reflect.py`, `test_ir_model_reflect_selection.py`, `test_ir_model_fields_constraints.py`, `test_ir_model_ondelete.py`.

**U3 — lectores tipo B dejan de ser latentes.** Tras U2, ya aciertan: `orm/models.py:3652`, `orm/environments.py:2235` (`_get(_name)`), `registry.py:2447` (`model__in=[m._name…]`), `account_demo.py:164`. Hay que **verificar el cambio de comportamiento** de `registry.py:2447` (empieza a ejecutar `_reflect_fields`, `_reflect_inherits`, selecciones y restricciones para las filas que antes no emparejaban) con una suite acotada; además `IrRule._check_model_name` (`:276`) deja de ser inerte. Pruebas: `tests/unit/orm/test_sql_error_to_message.py` (usa `IrModel._get('res.groups')`, 3 usos), `tests/unit/orm/test_registry_load_extended_models.py`, `tests/integration/test_orm/test_registry_caches_per_database.py`.

**U4 — `ir.rule.model_name`.** Decidir (ejecutor) entre mantenerla como etiqueta con `_sync_model_reference` traduciendo, o igualarla a `_name`. Si pasa a `_name`: `_get_rules`/`_compute_domain` y sus 6 llamadores (`ir_rule.py:531,549,579,637`, `orm/models.py:9083`) pasan a `reflected_name`; siembras (`base_security.py:33`, `sale/security/ir_rules.py:15`, `sale_subscription/security/ir_rules.py`) escriben `_name`. Razón del corte aparte: `@ormcache('model_name')` y el índice `db_index` cambian de clave; es el camino caliente de seguridad. Cubierta por: `tests/unit/base/test_ir_rule_model_id.py`, `test_ir_rule_access_error.py`, `tests/integration/test_orm/test_basemodel_access_against_rules.py`, `tests/integration/base/test_access_queryset.py`.

**U5 — ACL (`ir.model.access`).** Cambiar el cuello `label in _get_allowed_models(...)` (`ir_model.py:2788`), `_model_label` (`:2672`), `_make_access_error` (`:2938`) y `orm/models.py:413,420` a `reflected_name`. Va **después** de U2 (necesita la tabla ya en `_name`) y es el corte de más riesgo (cada petición del ORM pasa por aquí). Cubierta por los 3 archivos `test_ir_model_access_*` y `tests/unit/base/test_security_models_named.py`.

**U6 — clases sin `_name` (40 con contraparte).** Declarar `_name` en las que la fuente lo tiene, tarea prospectiva "se paga al tocar" (regla de atributos de clase); los 125 restantes quedan en `label_lower` sin cambio de clase. Razón: separa un cambio de **datos** (U2) de un cambio de **declaración** de modelos (cientos de archivos); no bloquea U2 porque `reflected_name` ya cubre el caso sin `_name`.

**U7 — contratos externos.** `addons/web/models/ir_model.py` (`display_name_for`, `get_available_models`) y `addons/base_automation/models/signals.py:65-68` (declaran "mismo formato que `IrModel.model`"): pasan a `reflected_name` y su divergencia documentada se corrige (`addons/web/controllers/export.py:72`). Si hay clientes UI que ya envían etiquetas, coordinar con `kaupamex-ui` (fuera del alcance de esta lectura).

Orden: U0 → U1 → U2 → U3 → U5 → U4 → U7, con U6 en paralelo y desacoplado.

## 7. Defectos latentes que el cambio expone (no son del plan, pero lo condicionan)

1. `IrModel._get(name)` (`ir_model.py:719`) y `_get_id` (`:736`) filtran por `model=name`; sus llamadores de `orm/` pasan `_name` (`orm/models.py:3652`, `orm/environments.py:2235`) mientras la columna tiene etiquetas: el `AccessError` implícito y el mensaje de error SQL **nunca** hallan la descripción hoy (caen al `_description`).
2. `registry.py:2447` (arriba).
3. `IrRule._check_model_name` compara con `'ir.rule'` y nunca puede ser verdadero con etiquetas (`'base.IrRule'`).
4. `IrModel._check_model_name` rechazaría cualquier etiqueta con mayúsculas si alguien llamara `clean()` en filas reflejadas.

## Métrica y ceguera

Métrica: conteos por `grep -rnE`/`grep -rnwE` sobre `src`, `addons`, `scripts`, `tests` (patrones citados en cada sección); recuento de modelos con `django.setup()` bajo `config.settings.testing` leyendo `registry.name_of` sobre `apps.get_models(include_auto_created=True)`; heurística camel→punteado contra los `_name` literales de `odoo19c/addons` y `odoo/` (1513). Se clasificó cada lector leyendo su contexto, no sólo el patrón.
Ciega a: (1) lectores que construyen el valor dinámicamente (`getattr`, `values(**{…})`, `model_id__model` formado con f-string, `related='crud_model_id.model'` heredado); (2) filas de datos ya sembradas en bases de producción (no se leyó ninguna base) y datos XML/CSV de módulos no cargados bajo `settings.testing`; (3) apps no instaladas en `testing` (el conteo 550/289/261 depende de `INSTALLED_APPS` de esa configuración); (4) la heurística camel→punteado falla con nombres de la fuente que no siguen el nombre de la clase (p. ej. `res.company.users.rel`), así que 40/125 es una **cota**, no una partición; (5) lo que los 49 archivos de pruebas esperan no se ejecutó (sin pytest, por mandato), sólo se clasificó por lectura; (6) clientes externos (UI, integraciones HTTP) que envíen etiquetas.
