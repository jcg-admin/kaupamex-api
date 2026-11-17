## Informe: afirmaciones sobre mixins en `account.journal` (solo lectura)

No modifiqué nada: no hubo `checkout`, pytest, migraciones ni escrituras. El store se abrió con `?mode=ro` desde Python, porque el binario `sqlite3` no está instalado.

**Antes de todo:** las líneas 17-37 del comentario **ya están en HEAD** (`1ff6e2a0`, 2026-11-08). Lo que no está commiteado (`git status` → ` M`) es otra cosa: el cambio de base `models.Model` → `models.BaseModel, TimeStampedModel`, los imports y unos campos One2many de payment methods.

### 1. Lo que afirma el comentario (`addons/account/models/account_journal.py`)
Lo leí con `sed -n 1,60p` (citas verbatim, en el archivo sin tildes):
- **Líneas 18-21:** sin `_name` el diario no entra en `orm.registry.MODELS_BY_NAME`, y sin él ni `linked_journal` resuelve su comodelo ni `_check_company_auto` tiene a quién preguntar **(tarea #333)**.
- **Líneas 25-27:** `_inherit` es *verbatim*, y "nombra la extension aunque el mixin aun no exista".
- **Líneas 27-31:** "Medido hoy: ``mail.thread`` y ``mail.activity.mixin`` SI estan (``addons/mail/models/mail_thread.py``); ``portal.mixin`` y ``mail.alias.mixin.optional`` NO — su porte es la tarea #163 (el hilo de mail sobre crm.team) y #161 (mail.alias.mixin) respectivamente."
- **Líneas 32-37:** `_inherit = ['portal.mixin','mail.alias.mixin.optional','mail.thread','mail.activity.mixin']`.

### 2. Qué existe hoy y qué hereda el diario
- **Clases con `_name`** (`grep -rn "_name = '<x>'" addons src`):
  - `mail.thread` en `addons/mail/models/mail_thread.py:51`.
  - `mail.activity.mixin` en `addons/mail/models/mail_activity_mixin.py:127`, no en `mail_thread.py`.
  - `portal.mixin`, `mail.alias.mixin.optional` y `mail.alias.mixin`: 0 resultados.
  - Pero `portal.mixin` **sí existe como clase**: `class PortalMixin(models.Model)` en `addons/portal/models/portal_mixin.py:36`, con un docstring que dice "≙ ``portal.mixin``", `Meta.abstract = True` y sin `_name`. La heredan `SaleOrder` (`sale/models/sale_order.py:124`) y `PurchaseOrder` (`purchase/models/purchase_order.py:123`, commit `0c6b0b9f` "Inherit the five source mixins on purchase.order").
  - En el árbol hay `mail.alias` (`mail_alias.py`), pero no hay ningún archivo de alias mixin.
- **Registro por nombre** (`src/orm/registry.py`):
  - `MODELS_BY_NAME` (`:315`) se puebla con `_register` (`:318-343`).
  - La entrada es el receptor de `class_prepared` (`:446-455`) más el barrido de `apps.get_models()` (`:497-502`).
  - Django no emite `class_prepared` para una clase abstracta: en `.venv/.../django/db/models/base.py` la rama `if abstract:` (`:379`) hace `return new_class` (`:385`) antes de `_prepare()` (`:387`). `get_models()` tampoco devuelve abstractas.
  - La única vía manual es `register_abstract` (`:428`), usada solo en `ir_fields.py:1006` e `ir_template_expressions.py:975`.
  - Conclusión: **ninguno de los cuatro mixins está en `MODELS_BY_NAME`**.
  - `AccountJournal` es concreto y declara `_name`, así que sí entra como `account.journal`.
- **Herencia real del diario** (lista de bases por AST): `AccountJournal ['models.BaseModel', 'TimeStampedModel']`. No hereda ningún mixin; tampoco en HEAD, donde la base era `models.Model`.

### 3. Qué hace este ORM con `_inherit`
- No encontré ningún código de ejecución que lea la lista `_inherit` de una clase (`grep "'_inherit'"`, `getattr(..'_inherit')`, `._inherit`).
- `Registry.descendants(..., '_inherit')` (`registry.py:3067-3112`) lee `_inherit_children` si la clase lo declara; si no, devuelve `()` (`:3110-3112`). No consulta `_inherit`.
- La extensión se hace con `extend_model(...)` (`model_classes.py:1522`, "≙ ``_inherit``") y con herencia Python (`model_classes.py:20,48`). El atributo `_inherit` no participa.
- **Efecto: `_inherit` es solo metadato.** No mezcla métodos ni campos; el comportamiento sale únicamente del MRO.

### 4. Ordinales → identidad canónica
Tabla `tasks` del store. Cada ordinal colisiona entre sesiones:
- **#161:**
  - `TASK-GEN-0413`, *"Portar mail.alias.mixin, y con el los cuatro simbolos de crm.team que lo esperan"*, **pending**, sesión `29a5e555…`. Encaja con el comentario.
  - Colisiones: `TASK-API-0097`, `TASK-THYROX-0404`, `TASK-THYROX-1096`.
- **#163:**
  - `TASK-GEN-0415`, *"Dar a crm.team el hilo de mail y los dos simbolos del panel"*, **pending**. **No trata de `portal.mixin`.**
  - Colisiones: `TASK-API-0099`, `TASK-THYROX-0406`, `TASK-THYROX-1079`, `TASK-THYROX-1098`.
  - Ninguna tarea menciona `portal.mixin` (0 resultados).
- **#333:**
  - Candidatas: `TASK-GEN-0060` (jsonb translate), `TASK-GEN-0585` ("delegacion del transitorio de account", in_progress), `TASK-GEN-0648`.
  - Ninguna menciona `MODELS_BY_NAME`, `account.journal` ni `linked_journal` (0 resultados), y las descripciones están vacías.
  - **DESCONOCIDO.** `TASK-GEN-0585` es la más cercana por tema, pero no la pude confirmar.
- Git y docs:
  - `git log -i --grep` en api no encontró ningún commit con estos ordinales: los tres que devuelve son de otros temas.
  - En docs, `mail.alias.mixin` aparece documentado (`cap20-correo.rst:291` "sin dueño"; `hallazgos-adaptar-familias-...rst:5587-5834`), sin ID de tarea.

### 5. Clasificación
| Afirmación | Clasificación | Evidencia |
|---|---|---|
| `mail.thread` "SI esta" | PARTIALLY_TRUE | La clase existe (`mail_thread.py:51`), pero no está en el registro por nombre y el diario no la hereda. |
| `mail.activity.mixin` "SI esta (mail_thread.py)" | PARTIALLY_TRUE | Existe, pero en `mail_activity_mixin.py:127`, no en `mail_thread.py`. No está registrada y el diario no la hereda. |
| `portal.mixin` "NO" | FALSE / OUTDATED | `PortalMixin` existe y la heredan sale y purchase. Lo que le falta es `_name`. |
| `mail.alias.mixin.optional` "NO" | VERIFIED_CURRENT | 0 clases. |
| porte de `portal.mixin` = #163 | WRONG_TASK_MAPPING | `TASK-GEN-0415` es el hilo de mail de crm.team. |
| porte de `mail.alias.mixin` = #161 | VERIFIED_CURRENT (mapeo) | `TASK-GEN-0413`, pending. Ojo: la tarea porta `mail.alias.mixin`, no la variante `.optional` que el diario nombra. |
| Sin `_name` no hay registro (#333) | Mecanismo VERIFIED_CURRENT; tarea UNVERIFIED | `_register` exige `_name` (`registry.py:330`). La tarea no se pudo resolver. |
| `_inherit` "nombra la extensión" | PARTIALLY_TRUE | Es solo metadato: no extiende nada (§3). |

### 6. Consumidores
`grep -rn "journal.*\.\(message_post\|activity_schedule\|alias_\|access_url\|access_token\)" addons src` → **0 resultados**. El modelo tampoco usa `message_`, `activity_`, `alias_` ni `access_url`. Ningún código depende hoy de que el diario sea un hilo de mail o tenga portal.

### Matriz
| Mixin | ¿Existe? | ¿Registrado? | ¿Lo hereda el diario? | Consumidores | TASK canónica | Clasificación |
|---|---|---|---|---|---|---|
| mail.thread | sí (`mail_thread.py:42,51`) | no (abstracto) | no | 0 | — | PARTIALLY_TRUE |
| mail.activity.mixin | sí (`mail_activity_mixin.py:122,127`) | no | no | 0 | — | PARTIALLY_TRUE (archivo citado incorrecto) |
| portal.mixin | sí como `PortalMixin`, sin `_name` (`portal_mixin.py:36`) | no | no | 0 | ninguna (#163 → TASK-GEN-0415 es otra) | FALSE + WRONG_TASK_MAPPING |
| mail.alias.mixin.optional | no | no | no | 0 | ninguna propia | VERIFIED_CURRENT (ausencia) |
| mail.alias.mixin | no | no | no | 0 | TASK-GEN-0413 (pending) | mapeo VERIFIED_CURRENT |

### Lo que no pude medir
- **No pude afirmar sin ambigüedad qué tarea es #333.** Las descripciones del store están vacías y hay tres candidatas, ninguna con el tema del comentario.
- **No comprobé en tiempo de ejecución el contenido de `MODELS_BY_NAME`** (no importé Django). La conclusión sobre el registro sale de leer el código de Django y el del registro.
- **No busqué consumidores indirectos**, por ejemplo uno que llame `message_post` sobre una variable que no contenga "journal" en su nombre.