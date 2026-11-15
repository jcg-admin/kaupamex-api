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
