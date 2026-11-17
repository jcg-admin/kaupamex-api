# Lote 0: consumidores de `AccountPayment` y contrato de la fuente

- Unidad: `account-payment-method-line-field-0515`
- Revisión base: `286faed0` (rama `feature/vm-x2hokp-orm-root`); referencia `odoo-tools@abe4040ec1`
- Fecha UTC: 2026-11-17T22:26:46Z
- Estado: COMPLETO para A, C, D, E, F; B con evidencia de código y UNVERIFIED en conducta (no se ejecutó nada).
- Cobertura: A evidencia · B parcial · C evidencia · D evidencia · E evidencia · F evidencia.

Convención: `odoo19c: <ruta>` es relativa a `R=/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0`.

## A. Consumidores de `AccountPayment`

Clase actual: `addons/account/models/account_payment.py:17` `class AccountPayment(models.Model)`, `_inherit` de mixins en `:23`; campos `amount`, `payment_type`, `partner_type`, `state`, `journal` (`:67`, null=False PROTECT), `partner` (`:73`, `AUTH_USER_MODEL`, SET_NULL), `currency`, `company`, `memo`, `is_reconciled` (`:43-110`).

### Sitios que CREAN pagos (todos `AccountPayment.objects.create`; ninguno usa `AccountPayment.create({...})`)

| # | Sitio | Diario | `partner` | `sudo` hoy | Qué rompería con (1)-(3) |
|---|---|---|---|---|---|
| 1 | `tests/integration/account/test_print_checks_endpoint.py:83` (helper `_payment`, `:70-83`) | `AccountJournal.objects.create(type='bank')` (fixture `:60-68`) | no | no (cliente HTTP `admin_client`; fixture `admin_user` `:32` ya añade `group_account_invoice`) | la ACL de `account.payment` exige `group_account_invoice` (`odoo19c: addons/account/security/ir.model.access.csv:113-114`); `objects.create` en la prueba corre sin usuario del cliente. Con (3) exige línea de método: el diario bank la recibe por el cómputo almacenado (ver B) |
| 2 | `tests/unit/account_check_printing/test_print_prenumbered_checks_wizard.py:58` (helper, `:46-58`) | `objects.create(type='bank')` (`:36-45`) | no | no (0 `sudo`) | sin entorno la lectura/creación pasa por `AccessManager`; necesita fixture autouse |
| 3 | `tests/unit/account_check_printing/test_account_payment_check_printing.py:62` (helper `:52-62`) | `objects.create(type='bank')` (`:46-49`) | no | **sí** (autouse `_as_superuser`, `sudo()`, 2 menciones) | sólo (3): la restricción exige línea manual saliente (`payment_type='outbound'`) |
| 4 | `tests/unit/account_payment/test_account_payment.py:51` (fixture `payment`) | `objects.create(type='bank')` (`:43-47`) | no (`partner_type='customer'`) | no | ídem 2 |
| 5 | `tests/unit/account_payment/test_account_payment.py:140` | mismo `journal`, `payment_type='outbound'` | no | no | ídem; además `AccountPaymentTransaction` FK al pago (`addons/account_payment/migrations/0001_initial.py:41,84`) |
| 6 | `tests/unit/account_payment/test_account_payment.py:182` | idem | no | no | ídem |
| 7 | `tests/unit/account_payment/test_account_payment.py:189` | idem | no | no | ídem |
| 8 | `tests/unit/account/test_account_core.py:260` (`TestAccountPayment.test_defaults`) | `objects.create(type='bank')` (`:257-259`) | no | no | ídem; el caso sólo aserta defaults de `payment_type/partner_type/state/is_reconciled` (`:264-267`) |

Hallazgo: son **8** sitios de creación, no 9 como dice `designs/payment-method-line-field.md` (cuenta hecha con `grep -rnE "AccountPayment\.objects\.create|AccountPayment\(|payment_set|account_payments"` sobre `tests addons src scripts`; el noveno no aparece. UNVERIFIED si el diseño contaba otro modelo).
Ningún sitio pasa `partner`: el cambio de destino de la FK no los rompe, sí rompe el `related_name` (ver C).
Ningún sitio es un diario `cash`/`credit`; todos `bank`. Con `type='bank'` el cómputo (`addons/account/models/account_journal.py:299-329`) da una línea manual de entrada y otra de salida (`_default_*_payment_methods`, `:62-63` de la fuente; siembra `account/0042` y `tests/conftest.py`).

### Lectores / FKs / otros

- `addons/account_check_printing/controllers/serializers.py:24`: `PrimaryKeyRelatedField(queryset=AccountPayment.objects.all())` (sólo pk). No lee `partner` ni método.
- `addons/account_check_printing/controllers/views.py:38` importa de `models.account_payment` (no del modelo base).
- `addons/account_check_printing/models/account_payment.py:159` importa `AccountPayment`; `:185` `OneToOne(AccountPayment, CASCADE)` (satélite `CheckPrintingPaymentInfo`).
- `addons/account_payment/models/account_payment.py:195-215` `apply_account_payment_extensions`: instala `payment_transaction`, `payment_token`, `source_payment` como propiedades sobre la clase. UNVERIFIED: si instalar propiedades sobre una clase `BaseModel` choca con el registro de campos (no lo medí).
- Migraciones con `RunPython` sobre pagos: **ninguna** (`grep AccountPayment` en `addons/*/migrations` sólo da `AddField/AlterField` en `account/0001,0002,0038` y las FK de `account_payment/0001` y `account_check_printing/0001:241`). `account/0042` siembra métodos, no toca pagos.
- Reversos con `related_name`: `journal.payments`, `company.payments`, `currency.payments` (`account_payment.py:70,86,92`) y `partner.account_payments` (`:78`). Lectores en `addons/` y `src/`: 0 (`grep -rnE "account_payments|\.payments\.(create|filter|all)"`; los `.payments` encontrados son de `sale_order.payments`, otro modelo).
- Migración `account/0038_model_headers.py:552-580` ya añadió `create_date`, `write_date`, `create_uid`, `write_uid` a `accountpayment`: la adopción de `TimeStampedModel` no requiere esas columnas (UNVERIFIED si el resto de estado coincide; no ejecuté `makemigrations --check`).

## B. ¿`objects.create` de un diario calcula sus líneas almacenadas?

Evidencia de código (sin ejecutar):

- `BaseModel._create` marca los cálculos con `modified(..., create=True)` bajo `protecting`: `src/orm/models.py:1203-1265`, y activa `ORM_CREATE_INSERTING` en `:1228`.
- Un alta por Django (`objects.create`/`save()`) la marca el receptor `post_save` `_modified_on_django_create` (`src/orm/models.py:6014-6058`): sale si `created` es falso, `raw`, o `ORM_CREATE_INSERTING` activo; si el modelo tiene algún campo `compute` y `store`, llama `modified(instance, list(registry), create=True)` bajo `target.protecting(protected, instance)`. Diseño: `designs/stored-computes-on-django-create.md`. No actúa sobre apps históricas (`:6041`).
- La marca deja el campo pendiente; la **lectura** de un One2many calculado almacenado pendiente recalcula antes de leer: `src/orm/fields_relational.py:556-559` (`if env.is_to_compute(self, instance.pk): self.recompute(instance)`).
- Conclusión: el camino `objects.create` SÍ calcula las líneas (al leer o al volcar), siempre que `AccountJournal` use `BaseModel` (lo hace desde `29285b00`) y exista entorno. UNVERIFIED en conducta: no ejecuté la prueba.
- Matiz documentado en el repo: `tests/unit/account_payment/test_account_journal.py:50-61` crea con `AccountJournal.create({...})` y hace `env().flush_all()` «si el cómputo quedara pendiente, su `Command.clear()` desligaría las líneas que la prueba añade después». Es decir: pendiente es distinto de calculado hasta el volcado o la lectura; un cómputo pendiente puede ejecutarse **después** de que la prueba añada líneas a mano.
- Los helpers de pago de A llaman `objects.create` del diario; el diseño usa `AccountJournal.create({...})` en `tests/unit/account/test_journal_payment_method_lines.py:49`.

## C. `partner`

- Lectores de `payment.partner` / filtros: ninguno en `addons/` ni `src/` (`grep -rnE "\.partner\b"` sobre `account_check_printing` y `account_payment`: 0; `account_payments` sólo en el modelo y migración `0002_initial.py:195`).
- Migraciones de `account` que tocan la columna: `0002_initial.py:186-199` (`AddField partner`, FK a `settings.AUTH_USER_MODEL`, SET_NULL, `related_name="account_payments"`). `0038_model_headers.py:552-580` sólo toca columnas de auditoría. Ninguna otra.
- De `ResUsers` a `ResPartner`: `ResUsers.partner = fields.Many2one('base.ResPartner', null=False, PROTECT, related_name='users')` en `src/addons/base/models/res_users.py:698`; tabla `res_users`, columna `partner_id` (el precedente usa `u.partner_id`).
- Precedente de cambio de destino con paso de datos: `addons/purchase/migrations/0011_order_partner_is_contact.py` (`purchase.order.partner_id`, de `res.users` a `res.partner`): `AlterField` a `BigIntegerField` (suelta la FK) → `RunSQL "UPDATE purchase_order po SET partner_id = u.partner_id FROM res_users u WHERE po.partner_id = u.id"` con reverso `noop` → `AlterField` a FK `to="base.respartner"`, `on_delete=PROTECT`. Dependencia `("base","0115_rescompany_purchase_fields")`. Cita del docstring: «se retira primero la FK, se traduce cada id al contacto de su usuario y sólo entonces se crea la FK nueva».
- Otro intento menos útil: `addons/crm/migrations/0002_alter_crmlead_partner_and_more.py` sólo renombra y mantiene `AUTH_USER_MODEL`.
- Fuente: `partner_id` es `res.partner`, `ondelete='restrict'` (`odoo19c: addons/account/models/account_payment.py:116-122`).
- Cuidado: usuarios cuyo `partner_id` sea NULL no existen (`null=False`), pero pagos con `partner` apuntando a un id de usuario inexistente quedarían huérfanos tras el `UPDATE` (el precedente no los trata). UNVERIFIED si hay datos así.

## D. `account_check_printing/models/account_payment.py`: inventario

- Lo que hace hoy: satélite `CheckPrintingPaymentInfo` (OneToOne a `AccountPayment`, CASCADE, `:185`) con `check_number`; la **existencia de la fila es el marcador** «este pago usa Cheques» (Divergencia 1, `:42-53`). Porta `show_check_number`, `amount_in_words`, `compute_check_number`, `set_check_number`, `validate_check_number_uniqueness`, `assign_check_number_on_post`, `prepare_print_checks`, `void_check`, `mark_as_sent`; `render_checks` bloqueado con `NotImplementedError` (Divergencia 7).
- Símbolos de la fuente (`odoo19c: addons/account_check_printing/models/account_payment.py`) que dependen del campo/código: `payment_method_line_id = Many2one(index=True)` `:30`; `_compute_show_check_number` `@depends('payment_method_line_id.code','check_number')` `:39-43`; `_compute_check_amount_in_words` `@depends('payment_method_line_id',...)` `:98`; `_compute_check_number` `@depends('journal_id','payment_method_code')` `:106-109`; `print_checks` filtra `payment_method_line_id.code == 'check_printing'` `:165`.
- Qué cambiaría al existir el campo: la Divergencia 1 queda OUTDATED (su afirmación «`grep payment_method` → 0 hits» pasa a falsa); el marcador por fila podría sustituirse por `payment_method_code == 'check_printing'`; `_get_payment_method_information` y la fila seed (`account_check_printing/migrations/0002_seed_check_payment_method.py`, `data/check_payment_method.py`) ya existen. Sin proponer reescritura: sucesor ya registrado en el diseño (unidad propia).
- Divergencias 5 y 8 dependen de `move_id`, no del campo; no cambian.

## E. Contrato fino de la fuente (`odoo19c: addons/account/models/account_payment.py`)

Transcripción literal:

```
565  @api.depends('available_payment_method_line_ids')
566  def _compute_payment_method_line_id(self):
570      for pay in self:
571          available_payment_method_lines = pay.available_payment_method_line_ids
572          inbound_payment_method = pay.partner_id.property_inbound_payment_method_line_id
573          outbound_payment_method = pay.partner_id.property_outbound_payment_method_line_id
574          if pay.payment_type == 'inbound' and inbound_payment_method.id in available_payment_method_lines.ids:
575              pay.payment_method_line_id = inbound_payment_method
576          elif pay.payment_type == 'outbound' and outbound_payment_method.id in available_payment_method_lines.ids:
577              pay.payment_method_line_id = outbound_payment_method
578          elif pay.payment_method_line_id.id in available_payment_method_lines.ids:
579              pay.payment_method_line_id = pay.payment_method_line_id
580          elif available_payment_method_lines:
581              pay.payment_method_line_id = available_payment_method_lines[0]._origin
582          else:
583              pay.payment_method_line_id = False
585  @api.depends('payment_type', 'journal_id', 'currency_id')
586  def _compute_payment_method_line_fields(self):
587      for pay in self:
588          pay.available_payment_method_line_ids = pay.journal_id._get_available_payment_method_lines(pay.payment_type)
589          to_exclude = pay._get_payment_method_codes_to_exclude()
590          if to_exclude:
591              pay.available_payment_method_line_ids = pay.available_payment_method_line_ids.filtered(lambda x: x.code not in to_exclude)
610  def _get_payment_method_codes_to_exclude(self):
612      self.ensure_one()
613      return []
620  @api.depends('payment_method_line_id')
621  def _compute_outstanding_account_id(self):
622      for pay in self:
623          pay.outstanding_account_id = pay.payment_method_line_id.payment_account_id
863  @api.constrains('payment_method_line_id')
864  def _check_payment_method_line_id(self):
868      for pay in self:
869          if not pay.payment_method_line_id:
870              raise ValidationError(_("Please define a payment method line on your payment."))
871          elif pay.payment_method_line_id.journal_id and pay.payment_method_line_id.journal_id != pay.journal_id:
872              raise ValidationError(_("The selected payment method is not available for this payment, please select the payment method again."))
```

Declaraciones de campo: `payment_method_line_id` `:74-84` (`readonly=False, store=True, copy=False`, `compute`, `domain` por `available_payment_method_line_ids`); `available_payment_method_line_ids` `:85-86` (M2M calculado, sin `store`); `payment_method_id` `:87-92` (`related`, `store=True`, `tracking`); `payment_method_code` `:176-177` (`related`, sin `store`); `outstanding_account_id` `:123-129` (`store=True`, `index='btree_not_null'`, `check_company=True`).

Observaciones de contrato (no obvias):
- `_compute_payment_method_line_id` depende **sólo** de `available_payment_method_line_ids` (`:565`); un cambio de `partner_id` por sí solo no lo recalcula (llega vía `journal_id`/`payment_type`/`currency_id`).
- El defecto de la preferida: sólo gana si su id está en las disponibles; si no, conserva la actual si sigue disponible; si no, la primera; si no, falso. Con `readonly=False` el valor escrito a mano sobrevive.
- La restricción nunca consulta `payment_type` y acepta una línea sin diario (`journal_id` falso en la línea).

`journal_id`, `currency_id`, `company_id` del pago en la fuente son **calculados almacenados, editables y precalculados**: `journal_id` `:23-29` (`compute='_compute_journal_id'`, `precompute=True`, `required=True`; cómputo `:427-445`: el diario de la línea preferida del partner; si no hay o la empresa no coincide, el primero `bank/cash/credit` de la empresa); `company_id` `:30-34` (`_compute_company_id`, `:447-451`, de `journal_id.company_id`); `currency_id` `:110-114` (`_compute_currency_id`, `:615-618`, de `journal_id.currency_id` o de la moneda de su empresa). En nuestro modelo los tres son **campos planos** (`journal` null=False sin default, `company` null=False, `currency` nullable; `account_payment.py:67-94`): crear sin `journal` falla, no se rellena. La prueba de la fuente `test_remove_payment_method_lines` (abajo) crea un pago sin `journal_id`; aquí no se podría.

### Pruebas de la fuente que ejercitan el campo

Archivos con la cadena: `addons/account/tests/{common,test_account_payment_register,test_account_payment_duplicate,test_account_journal,test_account_journal_dashboard,test_account_move_reconcile,test_account_payment,test_account_payment_method_line}.py` y `addons/account_payment/tests/{common,test_account_payment}.py`. Las que verifican el contrato de este paso (no sólo lo usan como parámetro de creación):

| Prueba | Qué comprueba |
|---|---|
| `account/tests/test_account_payment.py:530-547` `test_journal_onchange` | al cambiar el diario en el formulario, la línea es una del nuevo diario (`payment_method_line_id.journal_id == journal`), y al volver, del original |
| `account/tests/test_account_journal.py:106-130` `test_remove_payment_method_lines` | línea usada por un pago: `unlink` no la borra y `journal_id` queda falso (`:125`); línea sin uso: se borra. El pago se crea sin diario (`:116-121`) |
| `account/tests/test_account_journal.py:100-104` | tras crear el método `multi`, todos los diarios bank tienen la línea (parte de la unidad 2) |
| `account/tests/test_account_payment_method_line.py:34-36,44,56,116-131` | preferida del partner (`property_inbound_payment_method_line_id`) fija la línea del pago/asistente: `partner_a`→línea 1, `partner_b`→línea 2, `partner_c`→línea de otro diario (el pago cambia de diario) |
| `account/tests/test_account_payment_register.py:1536-1541,1553-1577` | `available_payment_method_line_ids` del asistente = líneas del diario y `payment_method_line_id` = la primera |
| `account/tests/test_account_payment.py:83,193,289,456,468` | creación con `payment_method_line_id` explícito de `bank_journal.inbound/outbound_payment_method_line_ids[0]` (uso, no contrato) |
| `account/tests/test_account_payment.py:123-125,322,439-440,518` | `payment_account_id` de la línea de método fija la cuenta de pendientes del pago (`outstanding_account_id`) |
| `account_payment/tests/test_account_payment.py`, `account_payment/tests/common.py` | pasarelas: lectura del código del método en pagos de proveedor (UNVERIFIED en detalle; no abrí el cuerpo) |

Sin ninguna prueba de la fuente para `_check_payment_method_line_id` por nombre (UNVERIFIED: `grep` por «Please define a payment method line» no se hizo; el criterio es de `grep "payment_method_line_id"` en las carpetas indicadas).

## F. `AccountPaymentMethodLine.unlink`

Fuente (`odoo19c: addons/account/models/account_payment_method.py:150-163`):

```
150  def unlink(self):
151      """ Payment method lines which are used in a payment should not be deleted from the database,
153      only the link betweend them and the journals must be broken. """
155      unused_payment_method_lines = self
156      for line in self:
157          payment_count = self.env['account.payment'].sudo().search_count([('payment_method_line_id', '=', line.id)])
158          if payment_count > 0:
159              unused_payment_method_lines -= line
161      (self - unused_payment_method_lines).write({'journal_id': False})
163      return super(AccountPaymentMethodLine, unused_payment_method_lines).unlink()
```

Nuestros llamadores que borran líneas hoy (`grep -rn "unlink"` + lectura):
- `AccountJournal.unlink`: `addons/account/models/account_journal.py:362-386` — `self.env['account.payment.method.line'].search([('journal_id','in',self.ids)]).unlink()` antes de `super().unlink()`.
- `AccountPaymentMethod.unlink`: `addons/account/models/account_payment_method.py:157-165` — `AccountPaymentMethodLine.search([('payment_method','in',self.ids)]).unlink()` (clave `payment_method` en `restrict`, migración `0041`).
- Los cómputos del diario usan `fields.Command.clear()` (`account_journal.py:305,337`). En el One2many la fuente borra la línea sólo si la FK inversa es `cascade` (`src/orm/fields_relational.py:712-731`); la línea tiene `journal` `on_delete=SET_NULL` (`account_payment_method.py:206-212`), así que `clear` anula `journal_id`, no borra. No pasa por `unlink`, luego no se ve afectado.
- Qué cambia con el `unlink` de la fuente: los dos llamadores pasan a conservar las líneas usadas (con `journal` nulo) en lugar de borrarlas; hoy `AccountJournal.unlink`, antes del cambio, las borraría y el `payment_method_line_id` del pago (nuevo FK) las gestionaría por su `on_delete`. Al ser `payment_method_line_id` `SET_NULL`, un `DELETE` directo dejaría el pago sin línea; el `unlink` evita ese estado.
- No hay otro llamador en `addons/`, `src/` ni `tests/` (`grep -rn "payment_method_line.*unlink"` fuera de `account_journal.py`: 0). Pruebas que borran: `tests/unit/account/test_journal_payment_method_lines.py` (`unlink` del diario, `:113`), `tests/unit/orm/test_restrict_ondelete_payment_method_line.py`.

## Comandos (decisivos, salida recortada)

```
$ git log --oneline -1
286faed0 Record the identity of the running full gate
$ grep -rnE "AccountPayment\b" --include=*.py tests addons src (recortado)
tests/integration/account/test_print_checks_endpoint.py:83:    return AccountPayment.objects.create(**defaults)
tests/unit/account_check_printing/test_print_prenumbered_checks_wizard.py:58:    return AccountPayment.objects.create(**defaults)
tests/unit/account_check_printing/test_account_payment_check_printing.py:62:    return AccountPayment.objects.create(**defaults)
tests/unit/account_payment/test_account_payment.py:51/140/182/189 ... AccountPayment.objects.create(
tests/unit/account/test_account_core.py:260:        p = AccountPayment.objects.create(
$ grep -c "sudo" <los cinco archivos>
test_account_payment.py:0 | wizard:0 | endpoint:0 | core:0 | check_printing:2
$ sed -n 6014,6058p src/orm/models.py        -> receptor post_save _modified_on_django_create
$ sed -n 556,559p src/orm/fields_relational.py -> if env.is_to_compute(self, instance.pk): self.recompute(instance)
$ sed -n 1,12p addons/purchase/migrations/0011_order_partner_is_contact.py -> precedente users->partner (AlterField, RunSQL UPDATE ... FROM res_users u, AlterField FK)
$ git -C /home/user/odoo-tools log -1 --format=%h   -> abe4040ec1
$ date -u                                    -> 2026-11-17T22:26:46Z
```

## No verificado / incertidumbres

1. UNVERIFIED en conducta (B): que `objects.create` de un diario calcule realmente sus líneas; la cadena de código lo implica pero no se ejecutó. La advertencia de `test_account_journal.py:51-61` sugiere un riesgo de orden entre cómputo pendiente y líneas añadidas a mano.
2. Nueve sitios (diseño) frente a ocho (medidos aquí): UNVERIFIED cuál falta.
3. `apply_account_payment_extensions` (propiedades sobre `AccountPayment`) con `BaseModel`: no medido.
4. Datos existentes: pagos cuyo `partner` apunte a un usuario sin partner o inexistente no tienen tratamiento en el precedente `purchase/0011`.
5. `journal`/`company`/`currency` planos: si el diseño espera crear pagos sin diario (como la prueba de la fuente), el cómputo de `journal_id` no está en el alcance de este paso.
