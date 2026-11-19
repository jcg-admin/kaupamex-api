# Inventory: porting `odoo19c: addons/mail/models/res_users.py` (660 lines)

ODOO19C = `/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0`. Source cited as `res_users.py:N` (= `ODOO19C/addons/mail/models/res_users.py`). Ours cited relative to `/home/user/kaupamex-api`.

*Metric:* `grep`/`sed` over the source file and over `src/`, `addons/` (`.py`); one runtime `issubclass(..., BaseModel)` check with `.venv/bin/python`.
*Blind to:* dependencies reached only through XML/QWeb templates, JS, or dynamic `env[...]` strings not matching my patterns; absence = zero grep hits in `.py`, not proof of semantic absence.

## 0. Verified facts about our tree

| Fact | Evidence |
|---|---|
| `base.ResUsers` is **not** `BaseModel` (`ResUsers False`; also `ResPartner`, `ResCompany`, `ResUsersSettings` False; `IrMailServer` True) | runtime check; `src/addons/base/models/res_users.py:471` `class ResUsers(models.DefaultGetMixin, TimeStampedModel)`; `ir_mail_server.py:283` `class IrMailServer(models.BaseModel, TimeStampedModel)` |
| Extension pattern for non-BaseModel: `extend_model('base','ResUsers', campos=, metodos=, propiedades=)` from `AppConfig.ready()`; non-stored computes go in `propiedades`/`store=False` fields | `addons/mail/models/res_company.py:81-107`, `addons/mail/apps.py:ready`, `addons/hr/models/res_users.py:618-660` |
| `extend_model` knobs: `campos, metodos, overrides, propiedades, selection_add, ondelete, indexes, luego` (no constraints knob; use `add_meta_constraint` via `luego`) | `src/orm/model_classes.py:1474-1476`, `:1702` |
| `extend_property(model, name, fn)` receives `anterior` (the super value); this is how `SELF_READABLE_FIELDS` is summed | `addons/hr/models/res_users.py:250-276`, `src/orm/model_classes.py:1573` |
| `hr` already installs `write` on ResUsers via `metodos` (`hr/models/res_users.py:319`, `:646`) — `mail`'s `write` override will chain with it | same |
| `email`/`name`/`phone` on ResUsers are inherited-related to partner (`_inherits`); **no** `email_normalized` on res.partner/res.users (only `crm_lead.py:424`); `tools.mail.email_normalize` exists | `res_users.py:766-770`; `src/tools/mail.py:291` |
| `share` is a property (`not _is_internal()`), not a column; `all_group_ids` M2M exists | `res_users.py:1839-1844`, `:2261`, `_compute_all_group_ids :1548` |
| `ir.config_parameter.get_param` exists (classmethod) | `src/addons/base/models/ir_config_parameter.py:150` |

## 1. Class header and fields

Header (`res_users.py:13-20`): `class ResUsers(models.Model)`, `_inherit = 'res.users'`, no `_name`. Only other class-level declaration: SQL constraint `_notification_type = models.Constraint("CHECK (notification_type = 'email' OR NOT share)", ...)` (`:70-73`). No `_order`, `_inherits`, `_rec_name`, etc. Imports reach: `request` (`odoo.http`), `Store` (`mail.tools.discuss`), `modules`, `tools`, `Command`.

13 fields:

| Field | Type / comodel | compute / related / default / groups | Line | Ours has equivalent? |
|---|---|---|---|---|
| `role_ids` | M2M `res.role`, relation `res_role_res_users_rel` | — | 22-27 | no `res.role` model. `addons/authz` has its own `role_ids` (different, capability model) — not equivalent |
| `can_edit_role` | Boolean | compute `_compute_can_edit_role`, `depends_context('uid')` | 28 | absent |
| `notification_type` | Selection email/inbox, required | default `'email'`, compute `_compute_notification_type` + inverse + **store=True**, depends `share`, `all_group_ids` | 29-36 | absent on users. `mail.notification.notification_type` etc. are other models' columns |
| `presence_ids` | O2M `mail.presence` (`user_id`), `groups=base.group_system` | — | 37 | absent (no `mail.presence`) |
| `out_of_office_from` / `_to` | Datetime | plain | 39-40 | absent |
| `out_of_office_message` | Html 'Vacation Responder' | plain | 41 | absent |
| `is_out_of_office` | Boolean | compute, depends the two dates | 42 | absent |
| `im_status` | Char | compute `_compute_im_status`, `compute_sudo=True`, depends `manual_im_status`, `presence_ids.status` | 44 | absent on users (`hr` has its own `im_status` on employees: `hr/models/hr_employee.py`) |
| `manual_im_status` | Selection away/busy/offline | plain | 45-48 | absent |
| `outgoing_mail_server_id` | M2O `ir.mail_server` | compute `_compute_outgoing_mail_server_id` (non-stored), `groups=base.group_user` | 50-55 | absent |
| `outgoing_mail_server_type` | Selection `[('default','Default')]` (extended elsewhere by google_gmail/microsoft_outlook via selection_add) | compute same method, `required=True`, default `'default'`, `groups=base.group_user` | 56-63 | absent |
| `has_external_mail_server` | Boolean | compute `_compute_has_external_mail_server` reading `ir.config_parameter` `base_setup.default_external_email_server` | 64 | absent |

`groups=` has no field-level counterpart to check here beyond the ORM; `base.group_user`/`base.group_system` exist as res.groups xmlids in our base (not re-verified).

## 2. Methods (25) and dependencies

Status legend: present / absent / present-but-not-BaseModel (pnb).

| # | Method | Lines | Purpose | Dependencies (status) |
|---|---|---|---|---|
| 1 | `_compute_has_external_mail_server` | 66-68 | flag from config param | `ir.config_parameter` present; key `base_setup.default_external_email_server`: **no Python hit** in our tree (declared only by `mail/models/res_config_settings.py:17` in source; our `addons/base_setup/models/res_config_settings.py` exists but has no such key) |
| 2 | `_compute_notification_type` | 75-95 | sync type with inbox group / portal | `all_group_ids` present; `ir.model.data._xmlid_to_res_id('mail.group_mail_notification_type_inbox')`: group exists in `addons/mail/data/mail_groups.xml:31` (res.groups record only); `Command.unlink`, `write(group_ids)` present; `share` pnb (property, not stored) |
| 3 | `_compute_is_out_of_office` | 97-109 | OOO window active | `env.cr.now()`, `_is_internal` present |
| 4 | `_compute_im_status` | 111-118 | status from presence + manual | `mail.presence` **absent** (only mentioned in `base/models/res_users.py:34,2394` comments and `authz_timeout/models/__init__.py`) |
| 5 | `_inverse_notification_type` | 120-124 | link/unlink inbox group | `env.ref('mail.group_mail_notification_type_inbox')` (group present as data); stored+inverse compute not supported on non-BaseModel -> needs `save()`/signal hook |
| 6 | `_compute_can_edit_role` | 126-128 | `res.role` write access | `res.role` **absent**; `has_access('write')` |
| 7 | `_compute_outgoing_mail_server_id` | 130-149 | find user's personal server by `from_filter`/`smtp_user`/`owner_user_id` | `ir.mail_server.from_filter`, `.smtp_user`, `.smtp_authentication` present (`ir_mail_server.py:306,338,330`); `ir.mail_server.owner_user_id` **absent** (only a doc mention `addons/mail/models/mail_alias_domain.py:51`); `email_normalized` absent -> use `tools.mail.email_normalize`; `user._origin.id` (ORM `_origin` exists in `src/orm`); `fields.Domain.AND/OR` present in orm |
| 8 | `SELF_READABLE_FIELDS` | 155-168 | adds 10 names | base property present `res_users.py:1403`; via `extend_property` (hr precedent) |
| 9 | `SELF_WRITEABLE_FIELDS` | 170-177 | adds 4 names | base present `:1435` |
| 10 | `create` | 179-195 | log portal access on partner | `_is_portal` present; `partner_id.message_post` -> `mail.thread.message_post` present in `addons/mail/models/mail_thread.py:99` but **ResPartner is not a MailThread** (pnb: `res_partner.py` has no `message_post`); `mail.mt_note` subtype xmlid (registered: `mail/migrations/0010_register_subtype_xmlids.py`); base ResUsers has no `create` model-method (Django `save`/manager `_create_user` at `:401`) -> hook point is `save()`/manager |
| 11 | `write` | 197-256 | portal log, security-update emails on login/password/email change, bus push of notification_type | `email_normalize` present; `_notify_security_setting_update` (#13, absent); `Store(bus_channel=user).add(...).bus_send()` — `Store` **absent** (`mail.tools.discuss` not ported); `addons/bus/models/bus.py:56` `BusMessage` exists but no Store/ `bus_send`; hr already installs `write` |
| 12 | `action_archive` | 258-261 | delete user's `mail.activity` then super | `mail.activity` present (`addons/mail/models/mail_activity.py:35`, `user` field name to confirm); `ArchiveMixin.action_archive` present (`src/orm/models.py:1620`) |
| 13 | `_notify_security_setting_update` | 263-315 | render `mail.account_security_alert`, create+send `mail.mail` | `mail.render.mixin` **absent** (mentioned in `digest.py`, `mass_mailing` but not defined); `mail.mail` present (`mail_mail.py:79`); QWeb templates `mail.account_security_alert` / `mail.mail_notification_light`: **absent** (`account_security_alert` string appears in `authz_totp_mail`, which has its own mailer); `company_id.partner_id.email_formatted` present (`res_partner.py:627`); `base.user_root` |
| 14 | `_notify_security_setting_update_prepare_values` | 317-350 | template values; GeoIP from `request` | `ir.config_parameter` key `auth_signup.reset_password` present (`addons/authz_signup/models/policy.py`); ambient `request.geoip` / user_agent **absent** by design (`res_users.py:1895-1900`: request passed explicitly) |
| 15 | `_get_portal_access_update_body` | 352-356 | text for the portal log | none (pure) |
| 16 | `_deactivate_portal_user` | 358-384 | log on partner, blacklist email, then super | `_deactivate_portal_user` exists only on **queryset/manager** (`res_users.py:289,386`), not on the model (pnb); `mail.blacklist` **absent** (`MailBlacklist` no hit); `partner._message_log` partner is not a thread |
| 17 | `_init_store_data` | 390-432 | discuss bootstrap data | `Store`, `mail.link.preview`, `mail.guest`, `res.users.settings._find_or_create_for_user` (present, `res_users_settings.py:84`), `_res_users_settings_format` (present `:96`), `ir.actions` xmlids `mail.action_discuss`: Store/guest/link-preview **absent** |
| 18 | `_init_messaging` | 434-454 | inbox/starred counters | `bus.bus._bus_last_id`, `partner._get_needaction_count` (**absent**), `mail.message.starred_partner_ids` (**absent**) |
| 19 | `_get_activity_groups` | 456-536 | systray activity groups | `mail.activity` present; `ir.model._get_id`, `_original_module`, `modules.module.get_module_icon` (to verify), `_filtered_access`, config key `mail.activity.systray.limit` **absent**; large, discuss/web-client oriented |
| 20 | `_get_store_avatar_card_fields` | 538-539 | Store field spec | `Store` **absent**; `partner._get_store_avatar_card_fields` **absent** |
| 21 | `_gc_personal_mail_servers` | 545-551 | autovacuum orphan personal servers | `@api.autovacuum`: `src/addons/base/models/ir_autovacuum.py` exists (hook name to confirm, no grep hit for `_gc_` pattern in mail); needs `owner_user_id` **absent** and #7 |
| 22 | `_get_mail_server_values` | 553-555 | hook returning `{}` | none |
| 23 | `action_setup_outgoing_mail_server` | 557-634 | create archived personal `ir.mail_server` for the user | `has_external_mail_server` (#1), `_is_internal`, `ir.mail_server._parse_from_filter` (present `ir_mail_server.py:725`), `_match_from_filter` (present `:734`), `mail.alias.domain.default_from_email` (present: `mail_alias_domain.py`), `tools.config['email_from']` (present `src/tools/config.py`), `owner_user_id` **absent**, `smtp_*` fields present, `outgoing_mail_server_type`/`_id` (#7), `_get_mail_server_setup_end_action` (#25), `_get_mail_server_values` (#22), `display_notification` client action (present as a pattern, `src/addons/base/models/ir_actions.py`) |
| 24 | `action_test_outgoing_mail_server` | 636-656 | test own server | `has_external_mail_server`, `has_group`, `outgoing_mail_server_id`, `IrMailServer.test_smtp_connection` (present `:599`) |
| 25 | `_get_mail_server_setup_end_action` | 658-660 | abstract hook, `raise NotImplementedError()` (implemented by google_gmail / microsoft_outlook, `grep -l` confirms both override it and `_get_mail_server_values`) | none |

## 3. Overrides of base methods and what our base offers

| Source override | Our hook |
|---|---|
| `SELF_READABLE_FIELDS` / `SELF_WRITEABLE_FIELDS` (`:155-177`) | properties at `res_users.py:1403,1435`; extend with `extend_property` (hr precedent). Note ours lacks several names the source base includes; `mail` just appends |
| `create` (`:179`) | none on the model; creation is `ResUsersManager._create_user` (`:401`) and `save()`; `ResUsers.save` goes through `TransactionClockSaveMixin` + `CheckCompanyMixin`. Would be a `save()` override or post-save signal (`src/addons/base/models/signals.py`) |
| `write` (`:197`) | no `write` in base; `hr` installs one via `metodos` — mail's must chain; `login`/`password`/`email` changes would be observed via `save(update_fields=)` or signals |
| `action_archive` (`:258`) | `ArchiveMixin.action_archive` (`src/orm/models.py:1620`) available on ResUsers (TimeStampedModel includes `ArchiveMixin`, `timestamped_mixin.py:92`) |
| `_deactivate_portal_user` (`:358`) | only queryset/manager variants (`res_users.py:289, 386`) — override target is the manager/queryset, not the model |
| model-level `_notification_type` Constraint (`:70`) | `Meta.constraints` through `add_meta_constraint` (`src/orm/model_classes.py:1702`); needs `share` as a column, which it is **not** (property): the CHECK cannot be expressed as-is |
| stored compute+inverse `notification_type` | non-BaseModel: no auto recompute; needs explicit `save()` hook |

## 4. `mail` data/security touching res.users

| File | What | Ours |
|---|---|---|
| `ODOO19C/addons/mail/data/mail_groups.xml:23-26` | `res.groups` record `group_mail_notification_type_inbox` (used by `notification_type`) | present: `addons/mail/data/mail_groups.xml:31` |
| `ODOO19C/addons/mail/data/res_partner_data.xml:10-12` | `base.user_root` `notification_type = inbox` | absent (needs field first) |
| `ODOO19C/addons/mail/data/mail_templates_mailgateway.xml:16-17` | `message_notification_out_of_office` template using `out_of_office_message` | absent |
| `ODOO19C/addons/mail/data/security_notifications_templates.xml` | `account_security_alert` QWeb (used by #13) | absent |
| `ODOO19C/addons/mail/security/ir.model.access.csv:24-25` | `res.role` access (user read, `group_erp_manager` full) | absent (no model) |
| `ODOO19C/addons/mail/security/ir.model.access.csv:36` | `mail.presence` `base.group_system` full | absent |
| `ir.model.access.csv:60`, `mail_security.xml:297-311` | `res.users.settings.volumes` access/rules | out of scope (settings model) |
| `ODOO19C/addons/mail/data/ir_cron_data.xml` | no res.users-specific cron (`_gc_personal_mail_servers` uses `@api.autovacuum`) | n/a |
| `mail/views/res_users_views.xml`, `res_config_settings.py:17` | views (not needed); config setting writing `base_setup.default_external_email_server` | not ported |
| our `addons/mail/security/authz_catalog.py` | capability catalog (authz) — would need entries if actions are exposed | present, unchecked |

## 5. Proposed split (dependency order)

Cross-cutting: all items extend ResUsers (non-BaseModel) via `extend_model('base','ResUsers', ...)`, one module `addons/mail/models/res_users.py` with `apply_mail_user_extensions()` called from `MailConfig.ready()`. Migrations needed whenever a column is added (`addons/mail/migrations/00NN`).

**Item A — personal outgoing mail server (smallest coherent; recommended first).**
Source scope: fields `outgoing_mail_server_id`, `outgoing_mail_server_type`, `has_external_mail_server` (`:50-68`); `_compute_outgoing_mail_server_id` (`:130-149`); `_get_mail_server_values` (`:553`), `action_setup_outgoing_mail_server` (`:557`), `action_test_outgoing_mail_server` (`:636`), `_get_mail_server_setup_end_action` (`:658`); `SELF_READABLE_FIELDS` additions for the three fields (`:165-167`); `_gc_personal_mail_servers` (`:545`) is the same feature (cleanup) and should be in or an immediate follow-on item.
Needs from `ir.mail_server` (`ODOO19C/addons/mail/models/ir_mail_server.py`), all absent in ours:
- `owner_user_id` M2O `res.users`, `copy=False` (`:20`) + `UNIQUE(owner_user_id)` constraint (`:29-32`); column on `IrMailServer` (BaseModel, so `campos=` works; constraint via `add_meta_constraint`/`luego`). Circular-ish FK: `mail` app config already depends on `base`.
- minimum hooks so a personal server is never used as a public one: `_filter_mail_servers_fallback` (`:80-82`, ours is a classmethod at `ir_mail_server.py:754`), `_find_mail_server_allowed_domain` (`:84-88`, ours classmethod `:1044` returns `Domain.TRUE`), `_check_forced_mail_server` (`:90-99`, ours `:1017`). Without these `owner_user_id` rows would leak into public selection — they belong in this item.
- `owner_limit_time` / `owner_limit_count` / `_get_personal_mail_servers_limit` (`:22-27, 101-106`) and `mail.mail` usage of owner (`mail_mail.py:348-349, 582, 711`) are throttling of personal sending: can be deferred to Item A2; the same applies to `mail_template_ids` (`:14-18`) and `_active_usages_compute` (`:34-41`).
Also needed: `base_setup.default_external_email_server` param (no setting in ours; read-only `get_param` is enough, writer is `res_config_settings.py:17` of source), `email_normalize` instead of `email_normalized`, `fields.Domain` OR/AND (present), `tools.config['email_from']` (present), `mail.alias.domain` (present). The missing `_check_default_from_not_used_by_users` in `mail_alias_domain.py` (documented pending `:44-53`, source `mail_alias_domain.py:175-178`) closes as a bonus once `owner_user_id` exists.
Design notes: `outgoing_mail_server_id/type` are non-stored computes -> `propiedades` (or `store=False` field like hr `employee_id`); `groups='base.group_user'` has no field-level enforcement in a `property`, must be enforced in the serializer/capability. `_get_mail_server_setup_end_action` stays abstract (`NotImplementedError`) as in source. `action_*` are `@api.model` methods that use `env.user`: need the current-user accessor `get_current_user` (`src/orm/environments.py`). Selection `[('default','Default')]` must stay extendable (`selection_add`).

**Item B — notification preference** (`notification_type`, `_notification_type` constraint, `_compute/_inverse_notification_type`, `base.user_root` data, SELF_* additions, bus push in `write` part). Needs: `share` as a column or rewrite constraint; stored compute+inverse on non-BaseModel (explicit `save()` hook); `group_mail_notification_type_inbox` (present). Bus push needs `Store` (absent) -> split the `bus_send` line out as pending.
**Item C — out-of-office** (`out_of_office_from/to/message`, `is_out_of_office`, SELF_* additions, OOO template). Self-contained (no missing deps beyond migration); independent of A and B.
**Item D — presence/IM status** (`presence_ids`, `manual_im_status`, `im_status`). Blocked by new model `mail.presence` (absent); then access CSV row.
**Item E — roles** (`role_ids`, `can_edit_role`). Blocked by new model `res.role` (+ access rows `ir.model.access.csv:24-25`); note name clash with `authz` roles.
**Item F — security notification mails + portal logging** (`create`/`write` overrides for portal log, `_notify_security_setting_update*`, `_get_portal_access_update_body`, `_deactivate_portal_user`, `action_archive`). Blocked by: ResPartner not being a MailThread (`message_post`/`_message_log`), `mail.render.mixin` + QWeb templates, `mail.blacklist`; `action_archive` alone (delete activities, `:258-261`) is small and can ship earlier (needs only `mail.activity`).
**Item G — discuss store** (`_init_store_data`, `_init_messaging`, `_get_activity_groups`, `_get_store_avatar_card_fields`, `:390-539`). Blocked by `Store`, `mail.guest`, `mail.link.preview`, `_get_needaction_count`, `starred_partner_ids`; web-client oriented, last/likely not ported as-is (needs a divergence decision).

Order: A (+A2 throttling) -> C -> action_archive piece -> B -> D/E (new models) -> F -> G.

**Hook-order caveat:** `hr` and `mail` both install `write` on `ResUsers` via `metodos`; `chain_method` makes the newer run first and the rest via relay. Whichever item first adds `write`/`save` behavior must be tested together with `hr` (`addons/hr/models/res_users.py:319`).
