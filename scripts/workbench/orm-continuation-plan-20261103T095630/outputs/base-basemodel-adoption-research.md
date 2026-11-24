# Investigación de solo lectura — `base` hacia `models.BaseModel`

Fecha: 2026-11-24T02:47:33 (`date -u`). Árbol: `api@0473d11b` (`git rev-parse --short HEAD`), referencia `odoo-tools@abe4040ec1`
(`git -C /home/user/odoo-tools rev-parse --short HEAD`), alias `odoo19c:` = `19.x/odoo-19.0/odoo-19.0/odoo-19.0`.
Forma: la de `stock-basemodel-adoption-research.md`, sección 6. No se editó código, no se corrió pytest ni se tocó PostgreSQL.

Instrumentos (scratchpad, `.venv/bin/python` con `django.setup()` sobre `config.settings.testing`, sin consultas a la base):
`/tmp/claude-0/-home-user/0390150a-c498-513f-9c46-273b863ccf3b/scratchpad/{intro,graph,an,rev,flip,cnt,objs,meth,acl,ord}.py`.
Nota: ese directorio es compartido y volátil; lo que sigue transcribe las cifras, no depende de él.

## 1. Las 49 clases

Método: `intro.py` recorre `apps.get_models()`, filtra `_meta.app_label == 'base'` y `_name` en la lista de 49, y emite archivo:línea
(`inspect.getsourcelines`), `__bases__`, los atributos de clase presentes en `m.__dict__` e `issubclass(m, orm.models.BaseModel)`.
Resultado: **49 encontradas, 0 son `BaseModel`**. Todas llevan `_table`; ninguna declara `_name` ausente.

Bases comunes (todas terminan en `TimeStampedModel` o en `Model` de Django): `RecordLoaderMixin`+`Model` (decimal.precision, config_parameter,
asset, autovacuum, cron.trigger, paperformat, ir.default, exports.line, country, country.state, lang, bank, currency, currency.rate,
partner.bank, ir.model.inherit); el resto `TimeStampedModel` con mixins (`OriginMixin`, `CopyMixin`, `DefaultGetMixin`, `AvatarMixin`).

| Unidad | `_name` | Clase | archivo:línea | `_order` | otros atributos de clase |
|---|---|---|---|---|---|
| U1 | decimal.precision | DecimalPrecision | `decimal_precision.py:22` | — | — |
| U1 | ir.config_parameter | SystemParameter | `ir_config_parameter.py:88` | `key` | — |
| U1 | ir.asset | IrAsset | `ir_asset.py:241` | `sequence, id` | — |
| U1 | ir.autovacuum | IrAutovacuum | `ir_autovacuum.py:121` | — | — |
| U1 | ir.profile | IrProfile | `ir_profile.py:368` | `session desc, id desc` | `_log_access=False`, `ProfileSetMixin` |
| U1 | report.paperformat | ReportPaperformat | `report_paperformat.py:270` | — | — |
| U1 | res.lang | ResLang | `res_lang.py:54` | `active desc,name` | — |
| U2 | ir.exports | IrExports | `ir_exports.py:33` | `name, id` | — |
| U2 | ir.exports.line | IrExportsLine | `ir_exports.py:67` | `id` | — |
| U2 | ir.ui.menu | IrUiMenu | `ir_ui_menu.py:306` | `sequence,id` | — |
| U3 | ir.module.category | IrModuleCategory | `ir_module.py:22` | `sequence, name, id` | — |
| U3 | ir.module.module | IrModule | `ir_module.py:133` | `application desc,sequence,name` | — |
| U3 | ir.module.module.dependency | IrModuleDependency | `ir_module.py:548` | — | `_log_access=False` |
| U3 | ir.module.module.exclusion | IrModuleExclusion | `ir_module.py:702` | — | — |
| U4 | ir.model | IrModel | `ir_model.py:345` | `model` | `OriginMixin` |
| U4 | ir.model.fields | IrModelFields | `ir_model.py:882` | `name, id` | `OriginMixin` |
| U4 | ir.model.fields.selection | IrModelFieldsSelection | `ir_model.py:1835` | `sequence, id` | `OriginMixin` |
| U4 | ir.model.inherit | IrModelInherit | `ir_model.py:1747` | — | `_log_access=False` |
| U4 | ir.model.constraint | IrModelConstraint | `ir_model.py:2234` | — | `CopyMixin` |
| U4 | ir.model.relation | IrModelRelation | `ir_model.py:2468` | — | — |
| U4 | properties.base.definition | PropertiesBaseDefinition | `properties_base_definition.py:127` | — | — |
| U5 | ir.model.data | IrModelData | `ir_model.py:2924` | `module, model, name` | `CopyMixin` |
| U6 | res.country | ResCountry | `res_country.py:72` | `name, id` | — |
| U6 | res.country.state | ResCountryState | `res_country.py:274` | `code, id` | — |
| U6 | res.currency | ResCurrency | `res_currency.py:169` | `active desc, name` | `CheckCompanyMixin` |
| U6 | res.currency.rate | ResCurrencyRate | `res_currency.py:891` | `name desc, id` | `CheckCompanyMixin` |
| U6 | res.bank | ResBank | `res_bank.py:123` | `name, id` | — |
| U7 | res.groups.privilege | ResGroupsPrivilege | `res_groups_privilege.py:29` | `sequence, name, id` | — |
| U7 | res.groups | ResGroups | `res_groups.py:144` | `privilege_id, sequence, name, id` | `CopyMixin` |
| U7 | ir.model.access | IrModelAccess | `ir_model.py:2595` | `model_id,group_id,name,id` | `_allow_sudo_commands=False` |
| U7 | ir.rule | IrRule | `ir_rule.py:172` | `model_id DESC,id` | — |
| U8 | ir.default | IrDefault | `ir_default.py:111` | — | — |
| U8 | ir.sequence | IrSequence | `ir_sequence.py:198` | `name, id` | — |
| U8 | ir.sequence.date_range | IrSequenceDateRange | `ir_sequence.py:517` | — | — |
| U9 | ir.ui.view | IrUiView | `ir_ui_view.py:271` | `priority,name,id` | — |
| U9 | ir.ui.view.custom | IrUiViewCustom | `ir_ui_view.py:935` | `create_date desc, id desc` | — |
| U10 | ir.actions.server | IrActionsServer | `ir_actions.py:1023` | `sequence,name,id` | base `IrActionsBase` (abstracta, 7 acciones) |
| U10 | ir.actions.server.history | IrActionsServerHistory | `ir_actions.py:886` | `create_date desc, id desc` | — |
| U10 | ir.actions.report | IrActionsReport | `ir_actions_report.py:427` | `name, id` | base `IrActionsBase` |
| U11 | ir.cron | IrCron | `ir_cron.py:397` | `cron_name, id` | `_inherits={'ir.actions.server': 'ir_actions_server'}`, `CheckCompanyMixin` |
| U11 | ir.cron.trigger | IrCronTrigger | `ir_cron.py:1517` | — | — |
| U11 | ir.cron.progress | IrCronProgress | `ir_cron.py:1570` | — | — |
| U12 | res.partner | ResPartner | `res_partner.py:148` | `complete_name ASC, id DESC` | `_check_company_auto=True`; `_inherit` de 4 mixins |
| U12 | res.partner.bank | ResPartnerBank | `res_bank.py:273` | `sequence, id` | `CheckCompanyMixin` |
| U13 | res.company | ResCompany | `res_company.py:259` | `sequence, name` | `_inherit` de 2 mixins |
| U14 | res.users | ResUsers | `res_users.py:476` | `name, login` | `_inherits={'res.partner': 'partner'}`; `AUTH_USER_MODEL` |
| U14 | res.users.apikeys | ResUsersApikeys | `res_users.py:2935` | — | `_auto=False` |
| U14 | res.device | ResDevice | `res_device.py:580` | `last_activity desc` | `_auto=False`, `_inherit=['res.device.log']` |
| U14 | res.device.log | ResDeviceLog | `res_device.py:255` | — | base `_ResDeviceFields` (abstracta) |

*Métrica:* `issubclass(m, BaseModel)` y `m.__dict__` por clase, sobre las 49 cargadas por `django.setup()`.
*Ciega a:* un atributo heredado de un mixin (sólo se listan los que la clase declara en su propio `__dict__`); y a que `_rec_name=None` que
aparece en algunas filas es el valor por defecto de la base, no una declaración.

### 1.1 ACL (`ir.model.access`)

El árbol **no tiene `security/ir.model.access.csv` en `base`** (`ls src/addons/base/security` → `base_security.py`, `ir_model_access.py`). El
rol del CSV lo cumple la tupla `_ACCESS` de `src/addons/base/security/ir_model_access.py:81`, derivada del CSV de la referencia y sembrada por
migración y por `tests/conftest.py`. Comparación (`acl.py`: `csv.DictReader` sobre
`odoo19c: odoo/addons/base/security/ir.model.access.csv` contra `_ACCESS`, mapeando label→`_name`):

| Cifra | Valor | Comando |
|---|---|---|
| filas de la referencia (`wc -l` − cabecera) | 146 | `wc -l odoo19c: odoo/addons/base/security/ir.model.access.csv` → 147 |
| filas de `_ACCESS` | 94 | `len(M._ACCESS)` |
| filas de la referencia para las 49 | **87** | `sum(ref['model_'+n.replace('.','_')] for n in NAMES)` |
| filas de `_ACCESS` para las 49 | **87** | `sum(mine[n] for n in NAMES)` |
| 49 con fila de `_ACCESS` ≠ fila de la referencia | **0** | diferencia por modelo, ver `acl.py` |
| de las 49, sin fila en la referencia | **4**: `ir.autovacuum`, `properties.base.definition`, `res.device`, `res.device.log` | idem |

Paridad completa: **no hay unidad 0 de ACL** como la U0-0 de `stock`; los grupos (`group_system`, `group_user`, `group_erp_manager`…) ya existen.
Los cuatro sin fila son iguales en la referencia (`rg -l 'model_res_device|model_ir_autovacuum|model_properties_base_definition' --glob '*.csv'`
sólo los halla en `base/security` como regla XML y en `mass_mailing`): un `BaseModel` sin fila rehúsa a quien no sea `su`. Es la conducta de la fuente; sus
consumidores (cron de `ir.autovacuum`, `res.device` por `sudo`) ya corren elevados, pero hay que **confirmarlo por unidad** antes de adoptar.

*Métrica:* filas de ACL por `model_id:id`, sólo identidad de modelo.
*Ciega a:* la paridad de los permisos y de los grupos fila a fila (el docstring de `_ACCESS` los copia verbatim; esta comparación sólo cuenta filas), y a los
cuatro modelos si otro addon siembra su ACL (`rg` no encontró ninguna en `addons/`).

## 2. Gráfica de relaciones

Método: `graph.py`/`rev.py`/`an.py` recorren `_meta.get_fields()` de los 454 modelos de `apps.get_models()` (`len(list(apps.get_models()))`), toman las relaciones
directas (no `auto_created`) cuyo dueño o destino sean de las 49, y registran dueño→destino, tipo, accesor inverso (`remote_field.get_accessor_name()`) y si cada
extremo es `BaseModel`. Hay **219 modelos `BaseModel`** en el árbol (`sum(issubclass(m, BaseModel))`), todos con `create_uid`.

### 2.1 Aristas entre las 49 (sin `create_uid`/`write_uid`)

90 aristas directas (`an.py`, sección `=====3`: «non-audit intra 90»); además **cada** una de las 49 apunta a `res.users` por `create_uid`/`write_uid`
(`LogAccessUserField`, que `rev.py` excluye). Salientes (dueño → destinos), sólo lo no trivial:

- `ir.model.fields` → `ir.model`, `res.groups` (M2M `groups`), y tres FK a sí mismo (`related_field_id`, `relation_field_id`, `serialization_field_id`).
- `ir.actions.server` → `ir.model` ×5, `ir.model.fields` ×3, `ir.model.fields.selection`, `ir.sequence`, `res.groups`, `ir.actions.server` (`parent`).
- `ir.actions.report` → `ir.model`, `report.paperformat`, `res.groups`. `ir.cron` → `ir.actions.server` (`_inherits`), `res.users`.
- `ir.model.access`/`ir.rule` → `ir.model`, `res.groups`. `ir.ui.view` → `res.groups`, `ir.ui.view` (`inherit_id`); `ir.ui.view.custom` → `ir.ui.view`, `res.users`.
- `res.partner` → `ir.actions.report` (`invoice_template_pdf_report_id`), `res.country`, `res.country.state`, `res.users` (×3), `res.partner` (×5).
- `res.company` → `report.paperformat`, `res.country`, `res.country.state`, `res.currency`, `res.partner`, `res.users` (M2M `user_ids`), `res.company` (`parent`).
- `res.users` → `res.company`, `res.groups` (M2M `all_group_ids`), `res.partner`. `res.groups` → `res.groups.privilege`, `res.users` (M2M `user_ids`), `res.groups` (3 M2M).
- Sin ninguna arista de entrada ni de salida entre las 49: `decimal.precision`, `ir.asset`, `ir.autovacuum`, `ir.config_parameter`, `ir.model.data`, `ir.profile`,
  `ir.ui.menu` (sólo `parent` a sí mismo), `res.lang`. Con sólo aristas de entrada: `report.paperformat` (desde `ir.actions.report` y `res.company`).

**Ciclos** (Tarjan sobre las aristas no auditoría, `an.py`): **1 componente fuerte de 5 nodos**:
`{ir.actions.report, res.company, res.groups, res.partner, res.users}` — por `res.partner.invoice_template_pdf_report_id → ir.actions.report → res.groups →
res.users → res.partner/res.company`, y los M2M `res.groups.user_ids ↔ res.users.group_ids`. Más 8 auto-referencias: `ir.actions.server`, `ir.model.fields`,
`ir.module.category`, `ir.ui.menu`, `ir.ui.view`, `res.company`, `res.groups`, `res.partner`.

A diferencia de `stock` (donde el ciclo `Warehouse↔PickingType↔Rule` obligaba a una sola unidad), **aquí el ciclo no impone una unidad única**: un FK entre un
`BaseModel` y uno que no lo es no cambia de tipo (la regla del enunciado), así que los miembros se pueden adoptar por orden y cada arista cae en la unidad del extremo tardío. Lo que
sí impone orden es el arranque (sección 5).

### 2.2 Radio de impacto de los cuatro modelos de base compartida

Aristas directas con dueño **`BaseModel` fuera de las 49** hacia cada destino (`an.py`, sección `=====`):

| Destino | campos (no auditoría) | modelos dueños | apps distintas | + auditoría |
|---|---|---|---|---|
| `res.company` | **67** | 67 | 21 | — |
| `res.currency` | **20** | 17 | 7 | — |
| `res.partner` | **41** | 34 | 13 | — |
| `res.users` | **46** | 35 | 22 | **436** campos `LogAccessUserField` (`create_uid`/`write_uid`) |

`res.country` 11 campos/10 modelos; `res.country.state` 3/3; `ir.sequence` 3/3; `res.lang` 3/2; `ir.module.module` 3/2; `ir.ui.view` 2/2; `res.bank`, `ir.model`, `ir.actions.server` 1/1.
`res.groups`, `ir.actions.report`, `report.paperformat`, `ir.module.category`: **0**. Hacia fuera, las 49 apuntan a `BaseModel` externos en 17 campos
(`res.company` → `project.Project`, `stock.StockLocation`, `account.AccountJournal` ×2, `uom.Uom` ×2, `product.ProductProduct`; `res.partner` → `ResCity`, `AccountPaymentMethodLine` ×2,
`StockLocation` ×2; `res.users` → `hr.HrEmployee`, `base.IrMailServer`; `ir.ui.view` → `website.WebsitePage`); el resto de sus FK externas va a modelos que **todavía no son** `BaseModel` (p. ej. `account.AccountAccount`).

*Métrica:* campos de relación directa con dueño `BaseModel`, por destino, con `LogAccessUserField` separado (se mide como `type(f).__name__`).
*Ciega a:* el reverso `GenericForeignKey`/`res_id` (p. ej. `ir.model.data.res_id`, que no es FK), el `related=`/`property` que se comporta como FK pero no es campo directo, y a que 1 de los 219 `BaseModel` declara `create_uid` con otro tipo que `LogAccessUserField` (436/2 = 218 modelos con el campo de auditoría tipado; el modelo 219 no se identificó).

### 2.3 Accesores que cambian al adoptar cada unidad

`flip.py` asigna cada arista a la unidad del extremo **tardío** (cuando ambos ya son `BaseModel`) y a la unidad del dueño `BaseModel` externo/destino. La lista nominal de
accesores directos e inversos por unidad es la de la tabla de la sección 4; el volumen está en 3.

## 3. Conteos de usos

Todos con `rg -n --type py -g '!**/migrations/**'` (las migraciones usan modelos históricos y no cambian). «prod» = `src` + `addons`; «tests» = `tests`. Formato `líneas/archivos`.
Patrones (`cnt.py`):
- *`is None`*: `\.(<campos directos que cambian>)\s+is\s+(not\s+)?None`.
- *API de gestor*: `\.(<accesores inversos>)\.(all|filter|exclude|add|remove|clear|set|create|get|first|last|count|exists|order_by|values_list|values|update|delete|select_related|prefetch_related|annotate|aggregate|get_or_create|update_or_create|bulk_create)\(`.
- *`.objects`*: `\b(<Clase>…)\.(objects|DoesNotExist|MultipleObjectsReturned)\b` (`objs.py`) — **no cambia de tipo**, pero marca el código que habla Django y no `BaseModel`.
- *sitios de `src/orm`*: `get_model\(\s*'base',\s*'<Clase>'\)|MODELS_BY_NAME(\.get\(|\[)'<nombre>'|model_by_name\('<nombre>'`.

| Unidad | `is None` prod | `is None` tests | API gestor prod | API gestor tests | `.objects` prod | `.objects` tests | sitios `src/orm` |
|---|---|---|---|---|---|---|---|
| U1 | 0/0 | 0/0 | 1/1 | 3/1 | 35/19 | 81/29 | 2/1 |
| U2 | 3/2 | 3/2 | 0/0 | 1/1 | 6/4 | 27/8 | 0/0 |
| U3 | 3/2 | 4/3 | 1/1 | 16/10 | 27/17 | 146/26 | 1/1 |
| U4 | 12/7 | 7/6 | 2/1 | 0/0 | 36/10 | 126/40 | 5/3 |
| U5 | 0/0 | 0/0 | 0/0 | 0/0 | 34/21 | 174/76 | 8/2 |
| U6 | 7/5 | 14/8 | 8/7 | 3/3 | 16/13 | 265/74 | 0/0 |
| U7 | 9/3 | 3/2 | 13/5 | **132/70** | 12/7 | 229/72 | 5/1 |
| U8 | 0/0 | 0/0 | 7/1 | 4/1 | 10/7 | 46/13 | 6/3 |
| U9 | 2/2 | 1/1 | 6/4 | 0/0 | 9/7 | 41/15 | 0/0 |
| U10 | 13/5 | 12/6 | 0/0 | 12/2 | 12/3 | 64/25 | 0/0 |
| U11 | 0/0 | 0/0 | 1/1 | 1/1 | 13/2 | 45/15 | 0/0 |
| U12 | 11/8 | 21/13 | 24/10 | 10/8 | 22/14 | 556/127 | 0/0 |
| U13 | 20/12 | 21/14 | 18/15 | 12/9 | 39/27 | 466/239 | 3/2 |
| U14 | 10/5 | 4/4 | **47/18** | **145/73** | 33/17 | 159/53 | 2/1 |

Otras cifras de base:
- `rg -n --type py -g '!**/migrations/**' '\.(create_uid|write_uid)\b' src addons` → 6; en `tests` → 1; `… is (not )?None` → **0** en las tres raíces (los 436 campos de auditoría que flipan con
  `res.users` casi no se leen como instancia).
- `rg -n '\brequest\.user\b'` → 179/44 prod, 8 tests; `get_user_model\(` → 8/6 prod, **194 tests**; `\.is_authenticated` → 9/6; `env\.user\b` → 115/62 prod, 48 tests;
  `env\.company\b|env\.companies\b` → 129/66 prod, 24 tests. `rg -n '\.prefetch_related|select_related'` (prod) → 103.
- Bucles `while x is not None` de cadena de padres dentro de las 49: `ir_module.py:117` (U3, `IrModuleCategory.parent`) y `addons/portal/models/res_partner.py:131` (U12, `res.partner.parent`).

*Métrica:* líneas de `rg` por patrón léxico sobre accesores derivados de `_meta`.
*Ciega a:* **atribución del dueño**: `parent`, `user`, `partner`, `company`, `country`, `state`, `groups`, `group_ids`, `child`, `children`, `journals`, `accounts`, `users` existen en otros modelos y se cuentan todos (los
conteos de U7, U12, U13 y U14 son cotas superiores); el reverso usado por variable local (`m = x.children; m.filter(…)`), `getattr`, plantillas (no se barrió `data/`, `report/`, `*.xml`), `values().annotate()` que
itera instancias, y `.objects` accedido por `apps.get_model` o alias de importación (sólo se cuenta el nombre de clase).

## 4. `write`/`create`/`delete`/`@api.ondelete` en las 49

`meth.py` (AST sobre `src/addons/base/models/*.py`, métodos `write|create|unlink|delete|save|copy|_check_access|clean|_get`):
- **`create(classmethod)`** (firma ajena a `BaseModel.create(self, vals_list)`): `decimal.precision`, `ir.config_parameter`, `res.currency`, `res.currency.rate`, `ir.default` — 5 clases.
- **`write(self)` redefinido** (a conciliar con `write(self, vals)`): `decimal.precision`, `ir.config_parameter`, `properties.base.definition`, `res.currency`, `res.currency.rate`, `ir.default` — 6.
- **`unlink(self)` redefinido**: `decimal.precision`, `ir.config_parameter`, `res.currency`, `ir.default` — 4.
- **`delete(self, **kw)` redefinido**: **20 de las 49** (conteo de la salida de `meth.py` por clase; no se leyó el cuerpo de cada una, así que cuántas hay que convertir en `unlink` con `@api.ondelete` es
  DESCONOCIDO hasta cada unidad). El único `@api.ondelete` ya presente es `ResUsers._unlink_except_master_data`.
- **`_get(classmethod)`**: `ir.module.module`, `ir.model`, `ir.model.fields`, `ir.default` — el nombre `_get` es de la fuente; no choca con `BaseModel`.

## 5. Dependencias de arranque: qué consulta `BaseModel` de `base`

`rg -n "get_model\(\s*'base'|model_by_name\('(ir|res)\.|MODELS_BY_NAME(\.get\(|\[)'(ir|res)" src/orm` → 34 sitios en 5 archivos. Los que importan, con lo que hacen hoy
(todos con **API de Django sobre el modelo de `base`**, que seguirá existiendo porque `BaseModel` es una base abstracta de Django, pero que en cada unidad hay que revisar):

| Modelo | sitios en `src/orm` | uso |
|---|---|---|
| `ir.model.access` | `models.py:410` | `Access.check(...)` y `_make_access_error`: **primera mitad** de `AccessQuerySet._check_access`. Internamente `ir_model.py:2731` lee con `cls.objects.filter(...)` (sin `check_access`), por eso no recursa. |
| `ir.rule` | `models.py:418, 9083, 10820` | `_compute_domain`/`_make_access_error`: **segunda mitad**; `ir_rule.py:421` también por `cls.objects`. |
| `ir.model.data` | `models.py:563, 1116, 2645, 4111, 9323, 9354, 11040`; `environments.py:1656` | `_update_xmlids`, `_lookup_xmlids`, `ref`, `bulk_create`, `.objects.filter(...).values_list(...)`: **todo** el cargador de datos y `get_external_id` |
| `ir.default` | `models.py:705`; `fields.py:942, 3361, 4966`; `fields_company_dependent.py:386, 403` | `default_get` y campos `company_dependent` |
| `ir.model` | `models.py:2627, 3651`; `environments.py:2235` | `_get`, `.objects.filter(...).values_list('name')` en el mensaje de error |
| `ir.model.fields` | `model_classes.py:808` | `_is_manual_name` **durante el montaje de clases** (arranque) |
| `ir.model.constraint` / `ir.module.module` | `models.py:3624` / `4177` | mensaje de restricción / `import_file` |
| `res.groups` | `models.py:2646` | `isinstance(group, ResGroups)` |
| `res.users` | `environments.py:187, 1138` | `env.user`: `ResUsers.objects.filter(pk=uid).first()` → `as_current_user` |
| `res.company` | `models.py:1909, 10236`; `environments.py:1159, 1168` | `env.company`/`env.companies`: `model.objects.filter(pk=…).first()`; `with_company` usa `company.pk` si no hay `_ids` |
| `res.lang` | `models.py:5685, 5804` | `env()['res.lang'].get_installed()` |
| `ir.config_parameter` | `models.py:1609` | `BaseUrlMixin` por `registry.model_by_name` |
| `res.currency.rate` | `models.py:7853` | `self.env['res.currency.rate']()` |

Dependencias circulares de arranque, identificadas:

1. **`check_access` de un `BaseModel` ↔ `ir.model.access`/`ir.rule`.** Adoptar estos dos como `BaseModel` hace que su propio `search`/`browse` pase por `check_access`, que llama
   a `Access.check` y `IrRule._compute_domain`. Hoy esas dos leen con `cls.objects` crudo (`ir_model.py:2731`, `ir_rule.py:421`), así que **no recursan**; la condición de U7 es
   que esas lecturas **no** se reescriban a `self.search`/`filtered` (precedente: la fuente las hace en SQL).
2. **`res.users` como actor.** `_check_access` y `_get_allowed_models` llaman `actor._get_group_ids()`, que hoy es `self.all_group_ids.values_list('pk', flat=True)`
   (`res_users.py:1484-1511`): API de gestor sobre el M2M `res.users.all_group_ids`. Al adoptar `res.users` **y** `res.groups` ese M2M pasa a recordset y el
   método debe reescribirse (`.ids`). Mientras `res.users` no sea `BaseModel`, todos los `BaseModel` de U1–U13 verifican contra un usuario Django: **por eso `res.users` va al final**.
3. **`ir.model.data` ↔ todo cargador.** `_load_records`/`_update_xmlids` escriben ahí; un `ir.model.data` `BaseModel` con `create` propio recargaría el mismo camino. `ir_model.py:3283` y `:3227` son
   `classmethod` de Django (`using=`); su firma no es la de `BaseModel` y la usan 8 sitios de `src/orm`. Unidad aparte (U5) y tras `ir.model`.
4. **`ir.default` ↔ `default_get`.** `BaseModel.default_get` (`models.py:705`) consulta `IrDefault._get_model_defaults` también para **`ir.default` mismo**; la lectura es
   cruda, no recursa, pero el `create(classmethod)` de `ir.default` debe pasar a la firma del recordset antes de que su `create` pase por `default_get`.
5. **`env.user`/`env.company` devuelven una fila de Django con `.objects.filter(...).first()`.** Al adoptar `res.company`/`res.users` esa fila es un singleton `BaseModel` (la misma clase), así que
   `env.company` sigue sirviendo; lo que cambia es todo `FK is None` que mire a `res.company`/`res.users` desde un dueño `BaseModel`: **67 campos/67 modelos** y **46 campos/35 modelos + 436 de auditoría**.
6. **`ResUsers` y `AUTH_USER_MODEL = 'base.ResUsers'`** (`config/settings/base.py:163`). `request.user` (179 usos prod), `get_user_model()` (194 en tests) y `is_authenticated` pasan a una clase con
   `__bool__`/`__len__`/`__iter__` de recordset. `BaseModel` instala la terna de singleton en `__init__` y `from_db`, así que `bool(user)` sigue siendo `True`; **no se midió** Django auth, simplejwt ni
   `AnonymousUser` bajo ese cambio (DESCONOCIDO, condición de cierre: ejecutar el subconjunto `tests/**/auth*` tras U14, o una sonda aislada antes).
   `inherits.py:43-47` ya declara que `ResUsers._create_user` resuelve el alta a mano porque no deriva de `BaseModel`; con la adopción pasa a `BaseModel.create` + `_inherits`.
7. **`_inherits` en `res.users`→`res.partner` y `ir.cron`→`ir.actions.server`.** Precedente: `product.product`→`product.template`, `mail.mail`. `ir.cron` obliga a que `ir.actions.server` sea `BaseModel` antes (U10 antes de U11) o en la misma unidad.
8. **`_order` con propiedades.** `BaseModel._order_to_sql` resuelve `self._fields[campo]`. `ir.cron._order='cron_name, id'` (`cron_name` es una `property`, `ir_cron.py:560`) y `res.company._order='sequence, name'`
   (`name` es `property`, `res_company.py:513`) **no son campos**; el resto de los 47 pasó la comprobación `ord.py` (`regex_order` + nombre en `_meta.get_fields()`/`attname`; `res.users`/`res.partner` pasan por ser
   campos o delegados). Hay que declarar `cron_name`/`name` como campo (calculado almacenado) o cambiar el `_order` en U11/U13.
9. **`_auto=False`** en `res.users.apikeys`, `res.device`: ningún `BaseModel` adoptado lo usa (`rg -n "_auto = False" src addons --type py` no se contrastó con `BaseModel`); DESCONOCIDO hasta una sonda en U14.
10. **`IrActionsBase` es abstracta y compartida por 7 acciones** (`ir_actions.py:258`): meter `BaseModel` ahí adopta a la vez `act_window`, `act_url`, `client`, `act_window_close`, que no están entre las 49 (no declaran `_name`). Alternativa: mixin sólo en las dos de la lista.

*Métrica:* sitios de `get_model('base', …)`/`MODELS_BY_NAME` en `src/orm` y lectura de los cuerpos citados.
*Ciega a:* las llamadas a estos modelos desde `src/` fuera de `src/orm` (`src/tools`, `src/addons/base/*`), las que van por `self.env[...]` con nombre dinámico (`models.py:4578`, `7283`…), y el
comportamiento en ejecución de cualquiera de los 10 puntos (ninguno se ejecutó: hay un gate corriendo).

## 6. Partición propuesta (en orden de dependencia)

Criterio: un FK/reverso cambia de tipo cuando **ambos extremos** son `BaseModel`; por tanto la carga de cada unidad cae en las aristas del extremo tardío. Orden: **destinos primero**
y, entre modelos de la misma capa, por **radio ascendente**: hojas sin FK, árboles pequeños, metadatos (`ir.module`, `ir.model`), `ir.model.data`, geografía/moneda (radio 10–26 modelos externos), seguridad,
`ir.default`/`ir.sequence`, vistas, acciones, cron, y los cuatro modelos de base compartida por radio: `res.partner` (41 campos/34 modelos) → `res.company` (67/67) → `res.users` (46 + 436 de auditoría). Cada unidad deja
la anterior verde antes de abrir la siguiente (lección de `sale`/`stock`). Suma de modelos: 7+3+4+7+1+5+4+3+2+3+3+2+1+4 = 49.

| Unidad | Contenido | Por qué en este orden | Accesores que cambian | Riesgos |
|---|---|---|---|---|
| **U1 — hojas sin FK** (7) | `decimal.precision`, `ir.config_parameter`, `ir.asset`, `ir.autovacuum`, `ir.profile`, `report.paperformat`, `res.lang` | Cero aristas entre las 49 salvo `paperformat` (entrada de `ir.actions.report` y `res.company`, que aún no son BM: no flipa). Sólo `res.lang` tiene reversos BM externos (`websites`, `default_websites`, `crm_leads`) | Ninguno intra. Externos: 3 campos/2 modelos (res.lang). 0 `is None`, 1 prod + 3 tests de API de gestor | `create(classmethod)`+`write`+`unlink` en `decimal.precision` y `ir.config_parameter`; `ir.autovacuum` sin ACL (cron bajo `su`); `res.lang.get_installed` usado por `src/orm` (2 sitios) y `config_parameter` por `BaseUrlMixin`; `ir.profile` con `_log_access=False` |
| **U2 — pequeños con árbol propio** (3) | `ir.exports`, `ir.exports.line`, `ir.ui.menu` | Sin dependencias fuera del par; `ir.ui.menu` sólo `parent` a sí mismo (`group`→`authz.Capability` no BM) | `export_id`, `parent`, `child`; 3 `is None` prod, 3 tests | `ir.ui.menu` es un árbol (`parent`): confirmar que ningún bucle de padres use `is not None`; `delete`→`unlink` |
| **U3 — módulos** (4) | `ir.module.category`, `ir.module.module`, `.dependency`, `.exclusion` | Destino de `ir.model.constraint/relation` (U4) y de `res.groups.privilege.category` (U7); sólo un árbol propio | `parent`, `child`, `category_id`, `modules`, `module`, `dependencies`, `exclusions`; 3+4 `is None`; 16 API de gestor en 10 archivos de test | **Bucle `while current is not None`** en `ir_module.py:117`; `IrModule.objects.using(...)` en `models.py:4177`; reversos externos `install_requests`/`install_reviews` |
| **U4 — metadatos de `ir.model`** (7) | `ir.model`, `ir.model.fields`, `ir.model.fields.selection`, `ir.model.inherit`, `ir.model.constraint`, `ir.model.relation`, `properties.base.definition` | Núcleo del que dependen U7 (ACL, reglas), U9–U11; el árbol de FK es acíclico salvo las 3 autorreferencias de `ir.model.fields` | 13 campos directos (`model_id`, `related_field_id`, `relation_field_id`, `serialization_field_id`, `field_id`, `parent_id`, `properties_field`…) y reversos `field_id`, `selection_ids`, `constraint_ids`, `relation_ids`, `inherit_*`, `inverse_of`, `related_from`, `sparse_field_ids`; 12 `is None` prod/7 tests | `src/orm` lo consulta en el **montaje de clases** (`model_classes.py:808`) y en errores (`models.py:2627,3624,3651`); 36 `.objects` prod; `IrModel._get`/`IrModelFields._get` classmethod; reflexión del registro (`ir.model` se siembra al arrancar) |
| **U5 — `ir.model.data`** (1) | `ir.model.data` | Sin FK, pero **todo cargador** pasa por él; se adopta después de `ir.model` para que `_update_xmlids` ya tenga su destino | Ninguno (sin FK) | 8 sitios de `src/orm` (`_update_xmlids`, `_lookup_xmlids`, `ref`, `bulk_create` con `using=`): firma de `classmethod` con `using=`; 34 `.objects` prod/174 tests; la semilla de `tests/conftest.py` y de `ir_model_access.py:532` corre `.objects.using(using)` — debe correr bajo `sudo` |
| **U6 — geografía y moneda** (5) | `res.country`, `res.country.state`, `res.currency`, `res.currency.rate`, `res.bank` | Destinos de `res.partner`/`res.company`/`res.partner.bank`; hojas respecto de ellos (el FK `res.currency.rate.company` flipa en U13) | `country`, `state`, `currency`, `banks`, `state_ids`, `countries`, `rates` + 23 reversos externos (`journals`, `move_lines`, `payments`, `pricelist_ids`, `crm_leads`, `hr_*`…): **35 campos/26 modelos BM externos**; 7+14 `is None`, 8+3 API de gestor | `res.currency` y `.rate` con `create(classmethod)`+`write`+`unlink` (5 firmas); `CheckCompanyMixin`; `models.py:7853` usa `res.currency.rate`; `res.country.currency` es el único FK intra |
| **U7 — grupos y política de acceso** (4) | `res.groups.privilege`, `res.groups`, `ir.model.access`, `ir.rule` | Tras U4 (FK `model_id`) y U3 (privilege→category). Son lo que lee `check_access`; `res.groups` se adopta **antes** de `res.users` (el M2M `user_ids` no flipa hasta U14) | `group_id`, `groups`, `privilege`, `category`, `implied_ids`, `all_implied_ids`, `implied_by_ids`, `access_ids`, `rule_ids`, `rule_groups`, `field_ids`, `group_ids`, `privileges`; 9 `is None` prod; **13 prod + 132 tests/70 archivos** de API de gestor (`.groups`/`.group_ids`; cota superior por nombres genéricos) | **Recursión de `check_access`**: `ir.model.access` y `ir.rule` deben seguir leyendo por `cls.objects` (punto 1); `_get_group_ids` (res.users) usa `all_group_ids.values_list` — no cambia hasta U14; `ir.model.access._allow_sudo_commands=False`; 87 filas de ACL en paridad |
| **U8 — `ir.default`, `ir.sequence`** (3) | `ir.default`, `ir.sequence`, `ir.sequence.date_range` | Hojas respecto de las demás; `ir.default` lo consume `default_get`/`company_dependent` (6 sitios de `src/orm`), y `ir.actions.server.sequence_id` (U10) apunta a `ir.sequence` | `date_range_ids`, `sequence` (intra); reversos externos `package_types`, `picking_types`, `lot_product_tmpls` (3 campos/3 modelos); 0 `is None`; 7+4 API de gestor | `ir.default`: `create(classmethod)`+`write`+`unlink`+`_get`; recursión de `default_get` consigo mismo (punto 4); los FK a `company`/`user` flipan en U13/U14 |
| **U9 — vistas** (2) | `ir.ui.view`, `ir.ui.view.custom` | Sólo dependen de `res.groups` (U7) y `ir.ui.view`; el reverso `inherit_children_ids` | `inherit_id`, `inherit_children_ids`, `ref_id`, `custom_ids`, `groups`, `view_access`, `first_page_id` (→`website.WebsitePage` BM), `configurator_features`/`page_ids` externos; 2+1 `is None`, 6 API de gestor prod | Árbol de herencia de vistas (`inherit_id`); `DefaultGetMixin`; `IrUiViewCustom.user` queda instancia hasta U14 |
| **U10 — acciones** (3) | `ir.actions.server`, `ir.actions.server.history`, `ir.actions.report` | Tras U4 (`model_id`, `link_field_id`…), U7 (`group_ids`), U8 (`sequence_id`), `report.paperformat` (U1); `res.partner.invoice_template_pdf_report_id` lo cierra U12 | 14 campos directos (`crud_model_id`, `update_field_id`, `webhook_field_ids`, `selection_value`, `parent`, `paperformat_id`, `group_ids`, `action`…) y reversos `code_history`, `server_actions`, `report_ids`…; 13 `is None` prod/12 tests; 12 API de gestor tests | **`IrActionsBase` abstracta compartida por 7 acciones** (punto 10); `ir.actions.server.parent`/`sequence_id`; `IrActionsServer.save` con revisión de código |
| **U11 — cron** (3) | `ir.cron`, `ir.cron.trigger`, `ir.cron.progress` | `ir.cron` `_inherits` `ir.actions.server` (U10); `trigger`/`progress` son hojas de `ir.cron` | `ir_actions_server`, `cron`, `crons`, `progress_ids`, `trigger_ids`; 0 `is None`, 1+1 API de gestor | **`_order='cron_name, id'` con `cron_name` property** (punto 8); `CheckCompanyMixin` y `company`; `delete`→`unlink`; la unidad `ir.autovacuum` (U1) invoca estos modelos |
| **U12 — `res.partner`** (2) | `res.partner`, `res.partner.bank` | Radio 41 campos/34 modelos/13 apps; antes que `res.company` (67) y `res.users` | 16 directos (`parent`, `commercial_partner_id`, `country`, `state`, `city_id`, `invoice_template_pdf_report_id`, `property_*`, `same_vat_partner_id`, `bank`, `currency`, `partner`) y **45 reversos** (`children`, `commercial_children`, `bank_accounts`, `partners`, `pickings`, `stock_moves`, `purchase_orders`, `journals`, `employee_ids`, `fleet_*`…); 11+21 `is None`; **24 prod + 10 tests API de gestor** | Bucle de padres `portal/models/res_partner.py:131`; `_check_company_auto=True`; `AvatarMixin`/`CopyMixin`; `delete`→`unlink`; `res.users` `_inherits` `res.partner` mientras `res.users` no es BM (`ResUsers._create_user`, `inherits.py:43-47`); `complete_name` en `_order` |
| **U13 — `res.company`** (1) | `res.company` | Radio 67 campos/67 modelos/21 apps: el mayor de los cuatro tras `res.users`; cierra los FK `company` de `ir.default`, `ir.sequence`, `res.currency.rate` | `parent`, `child_ids`, `partner`, `currency`, `country`, `state`, `paperformat`, `company` (en 3 modelos), `internal_*`, `sale_discount_product`… y 68 reversos (`journals`, `move_lines`, `sale_orders`, `stock_*`, `hr_*`, `resource_*`, `websites`…); 20+21 `is None`; **18 prod + 12 tests API de gestor** | **`_order='sequence, name'` con `name` property** (punto 8); `env.company`/`env.companies` (`environments.py:1159,1168`, 129 usos prod); `CheckCompanyMixin` en 67 modelos; ACL con `company_id` (`base_security.py` regla multi-company); `with_company` |
| **U14 — `res.users` + satélites** (4) | `res.users`, `res.users.apikeys`, `res.device`, `res.device.log` | Último: cierra el SCC de 5, el M2M `res.groups.user_ids`/`res.users.group_ids` y los 436 campos de auditoría; sólo después puede cambiar el actor de `check_access` | 16 directos (`company`, `partner`, `all_group_ids`, `employee_id`, `outgoing_mail_server_id`, `user`, `buyer_id`, `main_user_id`, `user_ids`…), 46 reversos (`users`, `group_ids`, `company_ids`, `api_keys`, `devices`, `sale_orders`, `project_tasks`…) y **436 campos `create_uid`/`write_uid` en 218 modelos BM** (0 `is None`; 6 usos prod, 1 test); **47 prod/18 archivos + 145 tests/73 archivos** de API de gestor | `AUTH_USER_MODEL`, `request.user` (179), `get_user_model` (194 tests), simplejwt/backends (DESCONOCIDO); `_get_group_ids` (`all_group_ids.values_list`); `_create_user` vs `BaseModel.create` con `_inherits`; `_auto=False` (apikeys, device); `delete`→`unlink` con `@api.ondelete` existente; `env.user` |

### 6.1 Qué grupos pueden ir primero con riesgo bajo

1. **U1 (7 hojas), con la salvedad de `res.lang`** — es la única de las 7 con reversos de `BaseModel` externos (3 campos/2 modelos) y con sitios en `src/orm` (2). Las otras seis
   (`decimal.precision`, `ir.config_parameter`, `ir.asset`, `ir.autovacuum`, `ir.profile`, `report.paperformat`) tienen **cero** accesores que cambien y sólo 1 prod/3 tests de API de gestor en
   toda la unidad. Recomendación: **U1 abre el programa**; `res.lang` puede ir al final de U1 o salir a una unidad propia si su subconjunto rojo no atribuye. Su costo real es de firmas
   (`create`/`write`/`unlink` de `decimal.precision` y `ir.config_parameter`) y de la ACL de `ir.autovacuum` (sin fila, igual que la fuente).
2. **U2 (3)** y **U3 (4)**: radio externo cero o dos modelos; U3 concentra tests de gestor (16 en 10 archivos) por `ir.module.module` (`modules`, `dependencies`).
3. **U11 antes que U10 no es posible** (el `_inherits` de `ir.cron` lo ata a `ir.actions.server`); sí lo es **U8 antes que U9/U10**, porque ni `ir.default` ni `ir.sequence` tienen FK hacia las demás.

### 6.2 Reconciliación transversal (que no cabe en una unidad)

`write(self)`/`create(classmethod)`/`unlink(self)` redefinidos en 5–6 clases de U1, U6 y U8 y los 20 `delete(self, **kw)` (a `unlink`) se resuelven con **una sola regla**
antes de U1, como pedía la reconciliación de `stock`: firma de `BaseModel`, `@api.ondelete` para el control previo, y las semillas de migración/`conftest` bajo `sudo` (porque `check_access`
las rehusaría sin elevación).

### 6.3 Alternativa descartada

Adoptar los cuatro modelos de base compartida a la vez («el SCC de 5»). Descartada: el SCC no obliga a una unidad única (sección 2.1), y juntos acumulan (suma de la tabla de la sección 3, U12–U14) 41 `is None` en prod y 46 en tests, y 89 usos de API de gestor en prod y 167 en tests, con 4 cambios de contrato de arranque (`env.user`, `env.company`, actor de `check_access`, `AUTH_USER_MODEL`) que un subconjunto
rojo no atribuiría (`alcance-de-la-suite.md`).

*Métrica:* clases por `django.setup()` + `_meta` (49 con `_name` fuera de `BaseModel`, 219 `BaseModel` en total, 454 modelos); aristas por `get_fields()`; accesores por `get_accessor_name()`; usos por `rg` con el patrón léxico de la sección 3;
firmas por `ast`; ACL por `csv.DictReader` contra `_ACCESS`; sitios de arranque por `rg` y lectura de los cuerpos citados.
*Ciega a:* un accesor con el mismo nombre en otro modelo (`parent`, `user`, `partner`, `company`, `groups`, `group_ids` aparecen en muchos; los conteos de U7, U12–U14 son cotas superiores y **ningún conteo atribuye el dueño de cada línea**); el reverso usado por
variable local, `getattr`, plantillas y XML (no se barrieron `data/`, `report/`, `views/`); `values().annotate()` que itera instancias; `.objects` accedido por alias o `apps.get_model`; el comportamiento en ejecución de los puntos
1–10 de la sección 5 (**DESCONOCIDO**: no se ejecutó nada porque hay un gate corriendo; condición de cierre: el subconjunto derivado de cada unidad más la suite de `tests/unit/orm`/`tests/integration/base` antes de U5 y de U14); los modelos de
`base` sin `_name` (no cuentan en el trinquete y quedan fuera: `IrAttachment`, `IrMailServer`, las otras acciones de `ir.actions.*`, `ResCountryGroup`, `ResCompanyUsersRel`…).
