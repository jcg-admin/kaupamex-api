# Seguridad de `account` — diseño (prerrequisito de la de purchase)

Unidad: `account-security-0121` (`TASK-API-0121`). Fuente:
`odoo19c: account/security/account_security.xml` (331 líneas) y
`account/security/ir.model.access.csv` (125 filas), LGPL-3.

## Por qué va antes que purchase

`purchase/security/purchase_security.xml` y su CSV citan
`account.group_account_invoice`, `account.group_account_manager` y modelos de
`account`. Sin esos xmlid la carga de purchase falla al resolver `ref`.
La máquina de estados de purchase (`button_approve` de dos niveles) no se
declara completa hasta que su seguridad esté cargada y probada con usuarios
autorizados y no autorizados.

## Precondiciones ya cumplidas

| Pieza | Dónde |
|---|---|
| xmlid `account.model_*` de 27 modelos | tramo A, `account-model-headers-0121` |
| `base.module_category_accounting` | `src/addons/base/migrations/0090_module_category_tree.py` |
| carga de `data` del manifest en el ciclo de instalación | precedente `addons/hr/__manifest__.py:28-31` |

## Forma (la del precedente de HR)

1. `addons/account/security/account_security.xml`: **copia fiel**. Cabecera con
   la procedencia (`odoo-tools@<rev>`) y cada omisión declarada con su causa
   medida, nunca en silencio.
2. `addons/account/security/ir.model.access.csv`: copia fiel **sin** las filas
   cuyo modelo no tiene fila en `ir.model` (medido 2026-11-15 sobre el
   registro, sin la base: 99 de 125 tienen modelo con `_name`). Las 26 se
   listan en el manifest con su causa: asistentes transitorios sin tabla,
   `account.invoice.report`, `account.root`, `account.code.mapping`, y las de
   `analytic.*` que se verifican contra la base con su prefijo de módulo.
3. `'data'` del manifest: `security/account_security.xml`,
   `security/ir.model.access.csv`, en ese orden (el de la fuente).

## Omisiones que se esperan, y cuál es su causa

- `group_account_manager.user_ids` (`base.user_root`, `base.user_admin`): esos
  usuarios no existen aquí (misma omisión que HR).
- Reglas cuyo modelo no tenga xmlid: se miden al cargar; ninguna se omite por
  suposición.
- Las reglas `[('company_id', 'in', company_ids)]` **no** se omiten por
  defecto: HR omitió las que evalúan `user.env.companies`; `company_ids` es
  otra variable del contexto de evaluación y se mide.

## Pruebas (RED primero)

- los diez grupos y los dos privilegios existen con su `implied_ids` y su
  privilegio, leídos de la fuente;
- cada fila del CSV cargada tiene su `ir.model.access` con los cuatro permisos
  de la fuente;
- las reglas de empresa filtran `account.move` por las empresas del usuario;
- un usuario sin `group_account_invoice` no lee `account.move`; con él, sí.

Anulación: retirar el CSV del manifest tiene que hacer caer exactamente las
pruebas de acceso y ninguna de las de grupos.

## Lo que este diseño no cierra

- `account_invoice_rule_portal` exige `user.commercial_partner_id`; se mide al
  cargar.
- La seguridad de purchase es la unidad siguiente (`purchase-headers-and-security-0397`,
  citada a `TASK-API-0122`).

## Medición de las 26 filas que no cargan (2026-11-15, sobre el registro)

Instrumento: filas del CSV de la fuente cuyo `model_<tabla>` no corresponde a
un modelo de `MODELS_BY_NAME` con `_name` propio.

| Causa | Filas | Modelos | Sucesor |
|---|---|---|---|
| modelo portado sin `_name` | 10 | `account.analytic.line`, `account.analytic.plan`, `account.analytic.applicability`, `account.analytic.distribution.model` (addon `analytic`), `account.invoice.report` | `analytic-model-headers-0121` |
| asistente transitorio abstracto (sin tabla, sin fila en `ir.model`) | 11 | secure_entries, automatic_entry, autopost_bills, resequence, validate_account_move, move_reversal, move_send, move_send_batch, accrued_orders, merge, merge_line | el mismo bloqueo que HR declaró; se cierra cuando los transitorios tengan tabla |
| modelo sin puerto | 5 | `account.root` (2), `account.code.mapping` (2), `account.payment.register` (1) | `account-unported-models-0121` |

*Ciega a:* un modelo registrado bajo otro `_name` que la fuente; la búsqueda por
literal del nombre en `addons/` y `src/` dio 0 para los tres sin puerto.

## Lo que la carga destapó (2026-11-15), y cómo se cerró

Cargar la copia fiel fue el instrumento: cada fallo del cargador nombró un
hueco que se cerró en el mismo pase o se declaró con su causa medida.

| Fallo al cargar | Causa | Desenlace |
|---|---|---|
| `implied_by_ids` con `Command.link` en `group_validate_bank_account` | el cargador sólo aplicaba comandos al lado directo de un muchos-a-muchos; en la fuente el inverso es otro `Many2many` sobre la misma tabla (`res_groups.py:197-199`) | **cerrado**: `_load_records_create` y `_pop_many2many_values` tratan `ManyToManyRel` igual que `ManyToManyField` |
| `('company_id', 'parent_of', company_ids)` rechazado | `IrRule._check_domain` traducía con `to_q(domain)` sin modelo; la fuente valida con `Domain(domain).validate(model)` (`ir_rule.py:70-72`) | **cerrado**: `_check_domain` en la forma de la fuente |
| `company_ids` en `account_comp_rule` | `account.account` está portado con `company` singular | **omitida**, declarada en la cabecera; sucesor `account-account-company-ids-0121` |
| `parent_state` en `account_invoice_line_rule_portal` | campo ausente en `account.move.line` | **portado**: `Selection(related='move_id.state', store=True)` + migración 0039 con cómputo de filas existentes |
| 0039 no calculaba sobre `account.move.line` | `ComputeStoredFields` invalidaba por `_fields`, que un modelo de Django no lleva | **cerrado**: invalida campo a campo por el registro |
| `model_res_partner` sin prefijo en el CSV | `account` extiende `res.partner` sin anotar la extensión, así que no recibía `account.model_res_partner` (`ir_model.py:462-475`) | **cerrado**: `apply_account_extensions` la anota con `note_model_extended_by` |

Resultado: 37 de 43 registros del XML y 99 de 125 filas del CSV, con las
siete omisiones del XML y las 26 filas del CSV declaradas con su causa.

Control de anulación: retirado `security/ir.model.access.csv` del manifest,
caen exactamente las 3 pruebas de acceso y siguen las 5 de grupos, reglas y
xmlid. La primera versión de la prueba no discriminaba —las filas venían de
la carga al crear la base— y la fixture las retira ahora antes de medir.
