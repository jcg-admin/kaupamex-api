# Informe — `account.journal` en la referencia Odoo 19 Community (solo lectura)

Referencia: `R=/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0`, `odoo-tools@abe4040ec1` (`git -C /home/user/odoo-tools rev-parse --short HEAD`). Solo usé `grep`, `sed -n` y `git rev-parse`. No escribí nada.

## 1. Atributos de clase de `AccountJournal`
Comando: `grep -nE "_name = |_inherit = |_description = |_order = |_check_company_auto|_check_company_domain|_rec_names_search" $R/addons/account/models/account_journal.py` y `sed -n 42,54p`.

- `class AccountJournal(models.Model)` — :42
- `_name = 'account.journal'` — :43
- `_description = "Journal"` — :44
- `_order = 'sequence, type, code'` — :45
- `_inherit = ['portal.mixin', 'mail.alias.mixin.optional', 'mail.thread', 'mail.activity.mixin']` — :46-50 (este es el orden real; `mail.alias.mixin.optional` va **segundo**)
- `_check_company_auto = True` — :51
- `_check_company_domain = models.check_company_domain_parent_of` — :52
- `_rec_names_search = ['name', 'code']` — :53

Hay otra clase en el mismo archivo: `account.journal.group` (:16-20). Declara `_check_company_auto` y `_check_company_domain` y no declara `_inherit`.

## 2. Los mixins del `_inherit`
Comando: `grep -rn "_name = '<m>'" $R/addons $R/odoo/addons` y `grep -n "^class"`.

| Mixin | Definido en | ¿AbstractModel? |
|---|---|---|
| `portal.mixin` | `addons/portal/models/portal_mixin.py:10` (clase `PortalMixin` :9) | sí |
| `mail.thread` | `addons/mail/models/mail_thread.py:127` (clase :63) | sí |
| `mail.activity.mixin` | `addons/mail/models/mail_activity_mixin.py:38` (clase :15) | sí |
| `mail.alias.mixin.optional` | `addons/mail/models/mail_alias_mixin_optional.py:17` (clase :11) | sí |

Lo que el diario consume de cada uno:
- **`mail.alias.mixin.optional`.** Es el único mixin que el diario consume de forma explícita y extensa.
  - Campos del mixin: `alias_id` (Many2one a `mail.alias`, `ondelete="restrict"`, no requerido, :21), `alias_name` (related, :22), `alias_domain_id` (:23), `alias_domain` (:26), `alias_defaults` (:27) y `alias_email` (:28).
  - El diario **redefine** `alias_name` solo para cambiar el `help` (`account_journal.py:258-260`).
  - Lee `alias_defaults` (:834) y `alias_domain` en un dominio (:874).
  - **Sobrescribe** `_alias_get_creation_values` (:829-842, llama a `super()` y fija `alias_model_id` = `account.move`). El mixin lo declara en :181.
  - Usa `_alias_get_creation_values` en `write` cuando cambia `type` (:805-812).
  - Métodos propios del diario: `_alias_prepare_alias_name` (:844), `_ensure_unique_alias` (≈:865-881), `_compute_display_alias_fields` (:308, que lee `mail.alias.domain`).
  - Llama a `mail.alias._sanitize_alias_name` y `mail.alias._is_encodable` (:772-773, :854, :858).
- **`mail.thread` / `mail.activity.mixin`.**
  - Comando: `grep -nE "_track|tracking=|message_|activity|_mail_"`.
  - Sin `message_post` ni `activity_*` explícitos en el archivo.
  - Solo hay un `message_values=` (:1280), que es un argumento de otra llamada (contexto de suscripción) y no una API del mixin.
  - No medí `tracking=` en los campos con un comando dedicado; el grep no los mostró. El consumo es implícito: chatter y actividades heredados.
- **`portal.mixin`.**
  - Aporta `access_url` (:13), `access_token` (:16), `access_warning` (:19) y `_compute_access_url` (:25).
  - Hay **0 usos** de `access_url`, `_compute_access_url` y `portal` en `account_journal.py`; el diario no los sobrescribe.
  - No medí si otros archivos (controladores o plantillas) usan `access_url` de un diario.

## 3. Cómo interpreta el ORM `_name` + `_inherit` en lista
Fuente: `odoo/orm/model_classes.py`, `add_to_registry` (:150-212). Comando: `grep -n "_inherit"` y `sed -n 150,212p`.

- :167-170 — `parent_names = list(model_def._inherit)` y se le añade `'base'`.
- :173-177 — **solo si `name in parent_names`** el modelo es una *extensión*: reutiliza `registry[name]` y exige que ya exista.
- :178-189 — si no, crea una **clase nueva**: `type(name, (model_def,), {...})`.
- :192-205 — cada padre distinto de `name` se añade a `bases`; se registra `_inherit_module[parent]` y `parent_cls._inherit_children.add(name)`.
- Cabecera explicativa :60-86: `_inherit = ['a', 'b']` con `_name = 'b'`; el MRO de `b` incluye `a`.

Para el diario, `'account.journal'` no está en su propia lista `_inherit`. Por eso se crea el modelo nuevo `account.journal`, cuyas bases son los cuatro mixins más `base` (herencia clásica, no delegación `_inherits`).

## 4. `unlink` / `@api.ondelete`
- **En `account`** (`account_journal.py`):
  - No hay ningún `@api.ondelete` (`grep -nE "ondelete\(|_unlink_except"` da 0).
  - Hay un override de `unlink()` en :724-733. Hace dos cosas:
    - Borra `account.payment.method.line` con `journal_id in self.ids` antes de `super()`.
    - Después borra las `res.partner.bank` de `bank_account_id` que ningún otro diario usa (`accounts <= self`).
  - Los campos con `ondelete='restrict'` hacia `account.account` están en :127 y :131, y hay otro en :249.
- **Extensiones:** el grep `_inherit = [?'account.journal'` dio **36** archivos. Solo dos tienen `ondelete`/`unlink`:
  - `addons/account_payment/models/account_journal.py:16-17`: `@api.ondelete(at_uninstall=False) _unlink_except_linked_to_payment_provider`. Lanza `UserError` si hay un `payment.provider` no deshabilitado con ese `journal_id`.
  - `addons/point_of_sale/models/account_journal.py`:
    - :25 `@api.ondelete(at_uninstall=False) _unlink_journal_except_with_active_payments`, que llama a `_check_no_active_payments`.
    - :30 `@api.ondelete(at_uninstall=True) _unlink_journal_cascade_pos_payment_methods`. Solo con `MODULE_UNINSTALL_FLAG` borra `pos_payment_method_ids` y los `pos.config` del diario.
- **No medido:**
  - Un `_inherit` de la forma `['account.journal', ...]` con otro elemento antes en la lista (el patrón exige que `account.journal` vaya primero).
  - Los `ondelete` de modelos que apuntan al diario (por ejemplo `account.payment.method.line`). Lo único comprobado es que `account_payment_method.py` no da hits para `ondelete(`/`_unlink_except`.

## 5. `payment_method_line_id` en `account/models/account_payment.py`
Comando: `grep -n "payment_method_line_id" …/account_payment.py`.

- **Definición** :74-79. Es Many2one a `account.payment.method.line`, `store=True`, `readonly=False`, `copy=False`, con compute `_compute_payment_method_line_id` y `domain` sobre `available_payment_method_line_ids`.
- **Escritura** (compute :565-583, `@api.depends('available_payment_method_line_ids')`):
  - Prioriza `partner_id.property_inbound/outbound_payment_method_line_id` (:572-577).
  - Si no, conserva el valor actual si está disponible (:578-579).
  - Si no, toma el primero disponible (:581); en último caso `False` (:583).
  - Las disponibles salen de `journal_id._get_available_payment_method_lines(payment_type)` (:588-591).
- **Lecturas:**
  - Related `payment_method_id` (:88) y `payment_method_code` (:177).
  - Cuentas de pago :248-250.
  - Etiqueta :271 y mensaje :326.
  - `outstanding_account_id = payment_method_line_id.payment_account_id`, compute con depends :620-623.
  - QR solo con `code == 'manual'` y pago saliente :649-655.
  - Copia a valores de otro pago :977 y mensaje :1138.
  - Nombre de propiedad del partner `property_{type}_payment_method_line_id` :433.
- **Restricción** :863-871: obligatorio, y la línea debe pertenecer al mismo `journal_id`.

**No medido:** consumidores fuera de `account_payment.py`, como `account.payment.register`, `account_payment` o `l10n_*`.
