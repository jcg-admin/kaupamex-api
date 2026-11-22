# U3-0 — ACL de `sale.order` y `sale.order.line` desde el manifiesto

Primera sub-unidad de la adopción de `BaseModel` en `sale`
(`outputs/sale-basemodel-adoption-research.md`). Sin estas filas, en cuanto
los dos modelos lean por el ORM, `check_access` los deniega a todo usuario
sin `sudo()`: el CSV tiene que existir **antes** de adoptar `BaseModel`, como
U0 lo hizo para `website`.

## Referencia

`odoo19c: addons/sale/security/ir.model.access.csv:28-39` — 11 filas para
los dos modelos (medido con `grep -nE "model_sale_order(_line)?,"`):

| Grupo | `sale.order` | `sale.order.line` |
|---|---|---|
| `base.group_portal` | 1/0/0/0 (`:28`) | 1/0/0/0 (`:35`) |
| `account.group_account_readonly` | 1/0/0/0 (`:29`) | 1/0/0/0 (`:36`) |
| `account.group_account_invoice` | 1/1/0/0 (`:30`) | 1/1/0/0 (`:37`) |
| `account.group_account_user` | 1/1/0/0 (`:31`) | 1/1/0/0 (`:38`) |
| `sales_team.group_sale_salesman` | 1/1/1/0 (`:32`) | 1/1/1/1 (`:39`) |
| `sales_team.group_sale_manager` | 1/1/1/1 (`:33`) | — |

Los cinco grupos existen en este árbol
(`addons/account/security/account_security.xml:76,81,94`,
`addons/sales_team/security/sales_team_security.xml`, `base`), y `sale`
depende de `account` y `sales_team` (`addons/sale/__manifest__.py:27-43`).

## Decisión

1. `addons/sale/security/ir.model.access.csv` con las 11 filas, verbatim
   (ids, nombres, grupos y permisos de la fuente).
2. `addons/sale/__manifest__.py` declara `'data': ['security/ir.model.access.csv']`
   (hoy no declara `data`).
3. El resto del CSV de la fuente (modelos que este árbol no tiene, o que no
   son `BaseModel`) queda fuera de esta sub-unidad; sus filas entran con la
   adopción de cada modelo.

## Símbolos, referencia y prueba

Prueba: `tests/unit/sale/test_sale_security_acl.py` — borra las filas que
dejó una carga anterior y comprueba que una instalación nueva (`load_data`
en modo `init`) crea exactamente las 11.

| Símbolo | Referencia | Prueba |
|---|---|---|
| 6 filas de `sale.order` | `odoo19c: addons/sale/security/ir.model.access.csv:28-33` | `test_sale_order_gets_the_source_acl` |
| 5 filas de `sale.order.line` | `odoo19c: addons/sale/security/ir.model.access.csv:35-39` | `test_sale_order_line_gets_the_source_acl` |

*Ciega a:* las reglas de fila (`addons/sale/security/ir_rules.py`), que esta
sub-unidad no toca, y al efecto de la ACL, que aparece al adoptar
`BaseModel` (U3a/U3b).
