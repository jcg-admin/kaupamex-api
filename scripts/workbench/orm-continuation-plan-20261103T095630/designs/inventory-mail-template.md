# Inventory: porting `mail.template` onto `BaseModel`

Source: `ODOO19C/addons/mail/models/mail_template.py` (828 lines, `wc -l`). `ODOO19C=/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0`.
Ours: `/home/user/kaupamex-api/addons/mail/models/mail_template.py` (161 lines). Read-only investigation; no file touched.
Metric: grep/ast over both trees. Blind to: runtime registry resolution (`_name` found by grep only), XML data/views, and any consumer that reaches the model via `apps.get_model`.

## 1. Class header

| | Source (`mail_template.py`) | Ours |
|---|---|---|
| class | `class MailTemplate(models.Model)` :17 | `class MailTemplate(TimeStampedModel)` :32 (no `BaseModel`) |
| `_name` | `'mail.template'` :19 | absent |
| `_inherit` | `['mail.render.mixin', 'template.reset.mixin']` :20 | none |
| `_description` | `'Email Templates'` :21 | none (Django `verbose_name='Plantilla de correo'` :122) |
| `_order` | `'user_id, name, id'` :22 | `Meta.ordering = ['name','id']` :121 (no `user_id`) |
| `_unrestricted_rendering` | `True` :24 | absent |
| table | `mail_template` | `Meta.db_table='mail_template'` :120 (same), index `mail_template_model_idx` on `model` |

Reference header to copy: `src/addons/base/models/ir_mail_server.py:283-290` (`class IrMailServer(models.BaseModel, TimeStampedModel)`, `_name`, `_description`, `_order`, `_allow_sudo_commands`).

## 2. Fields

Source fields at `mail_template.py:39-106`. "Ours" refers to `addons/mail/models/mail_template.py`.

| Field | Source type | Notes | Ours |
|---|---|---|---|
| `name` :39 | Char translate | | `name` Char(255) :37; **no translate** |
| `description` :40 | Text translate | | **absent** |
| `active` :43 | Boolean default True | | **absent** at field level (`TimeStampedModel` includes `ArchiveMixin`, `timestamped_mixin.py:91`; unverified that it adds `active`) |
| `template_category` :44 | Selection (base/hidden/custom), compute + search | | **absent** |
| `model_id` :49 | Many2one `ir.model`, ondelete cascade, domain non-abstract | | **absent** |
| `model` :50 | Char related `model_id.model`, stored, indexed, readonly | | `model` Char(128) :40, plain stored text holding `"app.Model"` labels (e.g. `sale.SaleOrder`), not the Odoo `_name`; semantics differ |
| `subject` :51 | Char translate prefetch | | `subject` Char :48; no translate |
| `email_from` :52 | Char | | present :54 |
| `user_id` :55 | Many2one `res.users`, domain `share=False` | | **absent** |
| `use_default_to` :57 | Boolean default True | | present :60, **default False** (mismatch) |
| `email_to` :63 | Char | | present :67 |
| `partner_to` :64 | Char (comma ids / placeholder) | | present :76 |
| `email_cc` :66 | Char | | present :85 |
| `reply_to` :67 | Char | | present :91 |
| `body_html` :69 | Html (`render_engine='qweb'`, `post_process`, `sanitize='email_outgoing'`, translate) | | `body_html` Html :97; Django-template syntax `{{ object.x }}`, no qweb/sanitize/translate |
| `attachment_ids` :73 | Many2many `ir.attachment` via `email_template_attachment_rel`, `bypass_search_access` | | **absent** |
| `report_template_ids` :79 | Many2many `ir.actions.report` via `mail_template_ir_actions_report_rel`, domain on `model` | | **absent** |
| `email_layout_xmlid` :85 | Char copy=False | | **absent** |
| `mail_server_id` :87 | Many2one `ir.mail_server`, index btree_not_null | | **absent** |
| `scheduled_date` :90 | Char | | present :110 |
| `auto_delete` :91 | Boolean default True | | present :116 |
| `ref_ir_act_window` :95 | Many2one `ir.actions.act_window`, readonly, copy=False | | **absent** |
| `can_write` :100 | Boolean compute (`depends_context uid`) | | **absent** |
| `is_template_editor` :102 | Boolean compute | | **absent** |
| `has_dynamic_reports` :105 | Boolean compute | | **absent** |
| `has_mail_server` :106 | Boolean compute | | **absent** |
| `lang` (from `mail.render.mixin:55`) | Char (expression) | | present :104 (Char(16), "language expression") |
| `render_model` (mixin :61) | Char compute, non-stored | | **absent** |
| `template_fs` (`template.reset.mixin:20`) | Char | | **absent** |

Totals: source declares 24 own fields (:39-106) plus 3 inherited via mixins (`lang`, `render_model`, `template_fs`). Ours has 12 of the 24 (name, model, subject, email_from, use_default_to, email_to, partner_to, email_cc, reply_to, body_html, scheduled_date, auto_delete) plus `lang`. Missing: description, active, template_category, model_id, user_id, attachment_ids, report_template_ids, email_layout_xmlid, mail_server_id, ref_ir_act_window, can_write, is_template_editor, has_dynamic_reports, has_mail_server.

## 3. Methods (34) and dependencies

Our class has only `__str__`, `_render_str` (static, Django `Template`), `render` (:130-161). None of the 34 exist by name.

| # | Method | Lines | Purpose | Depends on (status in our tree) |
|---|---|---|---|---|
| 1 | `default_get` | 26-31 | maps `model` default to `model_id` | `ir.model._get` present (`src/addons/base/models/ir_model.py:719`, class :350 is `OriginMixin, TimeStampedModel`, **not BaseModel**); `DefaultGetMixin` exists on `BaseModel` (`src/orm/models.py:6801`) |
| 2 | `_get_non_abstract_models_domain` | 33-36 | domain excluding abstract models | `env.registry` `_abstract`: `src/orm/registry.py:430` `register_abstract` present |
| 3 | `_compute_has_dynamic_reports` | 108-117 | counts reports per model | `ir.actions.report` present (`ir_actions_report.py:441`, class :427 `IrActionsBase`, not BaseModel); `_read_group` present (`src/orm/models.py:7364`) |
| 4 | `_compute_has_mail_server` | 119-122 | any mail server exists | `ir.mail_server` present, BaseModel (`ir_mail_server.py:283`) |
| 5 | `_compute_render_model` | 125-128 | mixin override | `mail.render.mixin` **absent** |
| 6 | `_compute_can_write` | 130-134 | `_filtered_access('write')` | present (`src/orm/models.py:459`) |
| 7 | `_compute_is_template_editor` | 136-138 | `has_group('mail.group_mail_template_editor')` | group XML present (`addons/mail/data/mail_groups.xml:22`); `ResUsers.has_group` present (referenced `res_users.py:258`); `res.users` has no grep-visible `_name` |
| 8 | `_compute_template_category` | 140-158 | base/hidden/custom from xmlid+description | `get_external_id` present (`src/orm/models.py:579`, :9184); `ir.model.data` present (`ir_model.py:2972`, TimeStampedModel) |
| 9 | `_search_template_category` | 160-181 | search method via xmlid subselect | `Domain` class: **absent** by grep in `src/orm/{models,fields}.py` (domains live in `src/orm/domains.py`, unchecked); `ir.model.data._search().subselect` unverified |
| 10 | `_onchange_model` | 183-189 | applies `_mail_template_default_values` | `@api.onchange` present (`src/orm/decorators.py:141`); `_mail_template_default_values` **absent** (0 hits) |
| 11 | `_fix_attachment_ownership` | 195-198 | writes res_model/res_id on attachments | `ir.attachment` present, BaseModel (`ir_attachment.py:80,95`) |
| 12 | `_check_abstract_models` | 200-206 | rejects abstract target models | `ir.model` present-but-not-BaseModel |
| 13 | `_check_can_be_rendered` | 208-231 | trial-render dynamic fields on create/write | `_render_field` **absent** (mixin) |
| 14 | `_get_dynamic_field_names` | 233-244 | set of 9 dynamic fields | none |
| 15 | `create` | 246-252 | `@model_create_multi` | `model_create_multi` present (`src/orm/models.py`, 2 hits) |
| 16 | `write` | 254-259 | check + fix attachments | as 13/11 |
| 17 | `unlink` | 261-263 | removes sidebar action | `ir.actions.act_window`: class `IrActionsActWindow` (`ir_actions.py:429`) **has no `_name`**; present-but-not-BaseModel |
| 18 | `copy_data` | 265-270 | "(copy)" suffix | `copy_data` present (`src/orm/models.py`) |
| 19 | `copy` | 272-291 | copies attachments | `ir.attachment.copy` |
| 20 | `unlink_action` | 293-297 | | act_window as 17 |
| 21 | `create_action` | 299-321 | creates sidebar act_window bound to `mail.compose.message` | `mail.compose.message` **absent** (0 `_name` hits; only mentions in `mail_thread.py`, `manual_notification.py`, `website_sale/models/sale_order.py`); view `mail.email_compose_message_wizard_form` **absent** (0 hits) |
| 22 | `action_open_mail_preview` | 323-326 | opens preview wizard | `mail.template.preview` **absent**; action `mail.mail_template_preview_action` **absent**; `_get_action_dict` present (`ir_actions.py:313`) |
| 23 | `_generate_template_attachments` | 332-405 | attachments + report PDFs | `ir.actions.report._render_qweb_pdf` (`ir_actions_report.py:2141`), `_render` (:1431) present; `report_type`, `print_report_name` present (:465, :525); `safe_eval` present (`src/tools/safe_eval.py:430`); hook `_process_attachments_for_template_post` has 1 implementer (`addons/account_edi/models/account_move.py`) |
| 24 | `_generate_template_recipients` | 407-510 | emails/partners from template or defaults | `tools.email_split` (`src/tools/mail.py:255`), `formataddr` (:396) present; `mail.thread._partner_find_from_emails` **absent** (only a comment in `hr_applicant.py:371`); `res.partner` present BaseModel; `_mail_get_companies`-style hooks **absent** |
| 25 | `_generate_template_scheduled_date` | 512-532 | | `_render_field`, `_process_scheduled_date` **absent** (mixin) |
| 26 | `_generate_template_static_values` | 534-565 | copies static config | none beyond fields |
| 27 | `_generate_template` | 567-652 | orchestrator per lang | `_classify_per_lang`, `_render_field` **absent** |
| 28 | `_parse_partner_to` | 654-665 | classmethod parse ids | none (pure) |
| 29 | `_send_check_access` | 671-673 | `check_access('read')` | present (`src/orm/models.py:400`) |
| 30 | `send_mail` | 675-697 | single send | 31 |
| 31 | `send_mail_batch` | 699-807 | builds `mail.mail`, layout, attachments | `mail.mail`: class `MailMail(TimeStampedModel)` (`addons/mail/models/mail_mail.py:79`), **no `_name`**, queue-based (`email_executor.dispatch_email` :63), no `mail_message_id`-style `send()` verified; `ir.config_parameter.get_param` present (`ir_config_parameter.py:150`); `tools.split_every` present (`src/tools/misc.py:596`); `_render_lang`, `_render_encapsulate`, `_mail_get_companies` **absent**; `with_prefetch` present (`src/orm/models.py:10110`); `mail.message` has no `_name` |
| 32 | `_has_unsafe_expression_template_qweb` | 813-816 | mixin override | mixin **absent** |
| 33 | `_has_unsafe_expression_template_inline_template` | 818-821 | mixin override | mixin **absent** |
| 34 | `_expression_is_default` | 823-828 | compare with model defaults | `_mail_template_default_values` **absent** |

## 4. Mixins

- `mail.render.mixin` (`ODOO19C/addons/mail/models/mail_render_mixin.py`, `models.AbstractModel`, 32 defs, fields `lang`, `render_model`): **absent** in our tree (`grep -rn "_name = 'mail.render.mixin'"` = 0). `addons/digest/models/digest.py` and `addons/mass_mailing/models/mailing_mailing.py` only mention it. Several of its methods back the template: `_render_field` :775, `_render_template` :657, `_classify_per_lang` :750, `_render_lang` :721, `_render_encapsulate` :168, `_process_scheduled_date` :644, `_has_unsafe_expression*` :268-298, `_is_restricted` :260, `_check_access_right_dynamic_template` :299, `_render_eval_context` :312, QWeb/inline render engines :336-624. Our rendering is a standalone Django-template `render()` (`mail_template.py:143`), which the reference QWeb/inline engines do not use. `ir.qweb` is ported (`src/addons/base/models/ir_template_expressions.py`) but only as a mechanism; wiring to a mail mixin is unverified.
- `template.reset.mixin` (`ODOO19C/addons/mail/models/template_reset_mixin.py:16`, AbstractModel, field `template_fs`, `create`, `_load_records_write`): **absent** (0 hits in src/addons).
- Both are AbstractModel; neither exists to be put on BaseModel.

## 5. Consumers in our tree (excluding the model file)

Command: `grep -rnE "MailTemplate|mail\.template|mail_template" src addons tests --include=*.py` (migrations excluded from the list below).

Direct code users (ORM `MailTemplate.objects`, attribute access):
- `addons/mail/models/mail_thread.py:37,198,339,361,385` — `template.render(...)`, `isinstance(source_ref, MailTemplate)`, `MailTemplate.objects.get(pk=)`; reads `rendered['subject'|'body_html'|'email_from']`.
- `addons/authz_signup/models/res_users.py:61,169,172,223,228` and `addons/authz_signup/data/__init__.py:22,82,86` — `.objects.filter(name=...)`, `.render(user, extra_context=...)`, seeding `create(**spec)`.
- `addons/authz_totp_mail/models/res_users.py:77,171,176,366,379` and `.../data/__init__.py:15,61,65` — same pattern.
- `addons/base_install_request/wizard/base_module_install_request.py:272` (`render`), `.../data/__init__.py:35,93,98` (`objects.using().create`, fields `model`, label `'mail.MailTemplate'`).
- `addons/account/wizard/account_move_send_wizard.py:108,366` — `MailTemplate.objects.create(...)` (uses text `model`).
- `addons/account/models/mail_template.py:37,71` — `chain_method(MailTemplate, 'delete', delete)` (master-template delete guard; not wired in `AccountConfig._EXTENSIONES` per its docstring).
- `addons/website_sale/models/website.py:174,276` (FK `cart_recovery_mail_template_id`), `addons/website_sale/models/sale_order.py:366,394,397` (`.render`, reads `email_to`, `partner_to`, `use_default_to`).
- `addons/hr_recruitment/wizard/applicant_refuse_reason.py:131` (`render`), `.../applicant_send_mail.py` (docs only), `models/hr_applicant_refuse_reason.py:31,44` and `models/hr_recruitment_stage.py:84` (FKs `'mail.MailTemplate'`).
- `addons/stock/models/res_company.py:538` (FK `'mail.MailTemplate'`), `addons/sale/models/sale_order.py:460-461` (FK `pending_email_template_id`).
- `addons/mail/models/__init__.py:37,61` (export), `addons/mail/models/notification_emails.py` (docs).
- `src/addons/base/report_template.py:17,162`, `src/addons/base/models/ir_actions_report.py:112-114` — prose/comments referencing `MailTemplate.render`/`_render_str`.

FKs by Django label `mail.MailTemplate`: 5 (hr_applicant_refuse_reason, hr_recruitment_stage, website_sale website, stock res_company, sale_order). Migrations touching it: `addons/mail/migrations/0001_initial.py`, `addons/sale/migrations/0008,0009`, `addons/website_sale/migrations/0001,0004`, `addons/authz_signup/migrations/0003`, `addons/base_install_request/migrations/0002`.

Tests: `tests/unit/mail/test_mail_thread.py:25,261-285` (`MailTemplate.objects.create`, `render`), `tests/unit/mail/test_message_post_with_source.py:15,88`, `tests/unit/stock/test_stock_picking.py:28,1169`, `tests/unit/website_sale/test_salesteam_migration.py:45-49`, `tests/integration/mail/test_mail_groups_data.py:41-88` (group only), `tests/unit/website_sale/test_abandoned_cart.py:473`.

Fields/methods consumed: `name`, `subject`, `body_html`, `email_from`, `email_to`, `partner_to`, `use_default_to`, `model`, `render(record, extra_context)`, `.objects` manager. Fields consumed that the reference does not have as written: Django `.objects`, label-style `model` (`'sale.SaleOrder'`).

Breakage risks of adoption: (a) `.objects` manager and `'mail.MailTemplate'` string FKs (5) must keep working; (b) `model` semantics (`app.Model` label vs `_name`) change if `model_id`/related `model` is adopted; seed code in 4 data modules writes `model` text; (c) `render()` return shape is consumed by 7 call sites and has no counterpart in the reference (`_render_field` returns per-res_id dicts), so it must stay as a compatibility shim; (d) `use_default_to` default flip (False→True) alters `website_sale/sale_order.py:397`; (e) adding `models.BaseModel` base changes MRO/registration—see how `IrMailServer` did it.

## 6. Proposed split (dependency order)

| # | Item | Content | Depends on | Size |
|---|---|---|---|---|
| 1 | Header on BaseModel | `class MailTemplate(models.BaseModel, TimeStampedModel)` + `_name='mail.template'`, `_description`, `_order='user_id, name, id'` (needs `user_id` field first, else interim `name, id`), `_unrestricted_rendering`; no behavior change; test registry resolution (`env['mail.template']`) and that 5 FKs / `.objects` / `render()` keep passing | none | S |
| 2 | Scalar fields | `description`, `active`, `email_layout_xmlid`, `template_fs`, `translate` on name/subject/body_html (check ORM translation support), `use_default_to` default decision (needs executor call), migration | 1 | S-M |
| 3 | Relational fields | `user_id` (res.users), `mail_server_id` (ir.mail_server, present), `attachment_ids` M2M ir.attachment with the two named relation tables, `report_template_ids` M2M ir.actions.report | 1 | M |
| 4 | `model_id`/`model` | `model_id` → `ir.model` + related stored `model`, `_get_non_abstract_models_domain`, `default_get`, `_check_abstract_models`, data migration of label text to ir.model rows; update 4 seed modules and `account_move_send_wizard.create_mail_template` | 1, 3; blocks 5-8 | M-L (highest consumer risk) |
| 5 | Computes and search | `template_category` (+ `_search_template_category`, needs `ir.model.data` subselect and Domain support), `can_write`, `is_template_editor`, `has_dynamic_reports`, `has_mail_server`, `_onchange_model`, `_get_dynamic_field_names` | 2, 4 | M |
| 6 | CRUD overrides | `create`, `write`, `unlink`, `copy_data`, `copy`, `_fix_attachment_ownership`, `unlink_action`; the account `chain_method(MailTemplate,'delete',…)` guard must be re-checked | 3, 4 | M |
| 7 | Render mixins (blocker for 8-10) | decide: port `mail.render.mixin` (32 defs; engines inline_template/qweb, `_render_field`, `_classify_per_lang`, `_render_lang`, `_render_encapsulate`, unsafe-expression checks) and `template.reset.mixin`, or keep Django-template `render()` and declare divergence. Needs executor decision; reference renders against `ir.qweb`/safe_eval, ours against Django `Template` | 1 | L (split in 2-3 once decided) |
| 8 | `_check_can_be_rendered` + `_generate_template*` (5 methods) + `_parse_partner_to` | recipients need `mail.thread._partner_find_from_emails` (absent) and company hooks; attachments need `ir.actions.report._render_qweb_pdf` (present) and `_process_attachments_for_template_post` hook (1 implementer: account_edi) | 7, 3, 4 | L |
| 9 | `send_mail`, `send_mail_batch`, `_send_check_access` | map onto `mail.mail` queue (`MailMail` has no `_name`, delivery goes through `email_executor.dispatch_email`); needs `mail.mail`/`mail.message` naming or an adapter | 8 | M-L |
| 10 | Sidebar action and preview | `create_action`, `action_open_mail_preview`, `ref_ir_act_window`; requires `mail.compose.message`, `mail.template.preview`, their views/actions—all absent; likely defer (separate initiatives) or declare divergence | 4 | M (+ new models if ported) |

Recommended first slice: items 1 and 2 (no consumer behavior change, small), then 3. Item 4 and the render decision (7) are the two risk concentrations and require explicit decisions before work starts.
