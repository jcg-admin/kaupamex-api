# TASK-GEN-0356 — `ResUsers.share` como Boolean calculado y almacenado

Fuente: `odoo19c: odoo/addons/base/models/res_users.py:234-235` (campo) y
`:459-464` (`_compute_share`), con sus consumidores en
`odoo19c: odoo/addons/base/models/res_partner.py:335-357,425-448`.
Investigación: borrador `research/base-res-users-share-field-0356.md`
(scratchpad), con las decisiones del orquestador del 2026-11-25.

## Contrato

```python
share = fields.Boolean(compute='_compute_share', compute_sudo=True,
                       string='Share User', store=True, ...)

@api.depends('all_group_ids')
def _compute_share(self):
    user_group_id = self.env['ir.model.data']._xmlid_to_res_id('base.group_user')
    internal_users = self.filtered_domain([('all_group_ids', 'in', [user_group_id])])
    internal_users.share = False
    (self - internal_users).share = True
```

- **Regla literal** (decisión 1): interno ⇔ `base.group_user ∈ all_group_ids`.
  No se usa `ResGroups.user_type`: la fuente tiene el método
  `_get_user_type_groups`, no un campo. Los tests ajenos que hoy fijan `share`
  con un grupo propio de `user_type='internal'` pasan a dar `base.group_user`,
  como los de la referencia.
- Retira `@property share` (`res_users.py:1843-1849`), que choca con el campo.
- `SELF_READABLE_FIELDS` gana `'share'` (`odoo19c: res_users.py:185`).
- `default=True` es divergencia declarada, como `IrRule.global`: la fila se
  inserta antes que sus grupos y es lo que el cómputo da sin grupos.
- Migración nueva con `AddField` + `ComputeStoredFields('base', 'resusers',
  ['share'])` (REUSE de `src/orm/migration_operations.py`). El número se toma
  con `ls` al escribirla.
- `res_partner`: `_compute_main_user_id` recupera `'users.share'` en su
  `@api.depends` (≙ `:425-426`); los cuerpos de `_compute_partner_share` y
  `_compute_avatar` pasan a `not user.share` (decisión 3, ≙ `:357,448`).

## Corrección al borrador: el aviso Many2many ya llega

El borrador proponía `_mark_share_for_recompute` en los receptores porque
suponía que el puente M2M sólo avisa al lado declarante. La unidad
`orm-m2m-modified-inverse-side-0356` lo midió y es falso: el recorrido de
`field_inverses` en `_modified_triggers` llega a los dependientes del inverso
(`designs/orm-m2m-modified-inverse-side-0356.md`, addendum). Esta unidad **no
añade marcado propio** (decisión 2); si un caso de recálculo cae, la causa se
mide antes de añadir nada.

## Tests ajenos afectados (decisión 1), medidos

`grep -rn -E "\.share\b|main_user_id|partner_share|_compute_avatar" tests/`
(sin el `share` de grupos):

| Archivo | Lecturas |
|---|---|
| `tests/integration/base/test_res_partner_avatar.py` | 10 |
| `tests/integration/base/test_res_partner_labels.py` | 9 |
| `tests/integration/base/test_res_partner_user_and_lang.py` | 12 |
| `tests/integration/base/test_res_users_user_type.py` | 4 |
| `tests/unit/digest/test_digest.py` | 1 |
| `tests/unit/digest/test_digest_signals.py` | 3 |

Cuáles caen de verdad lo dice el subconjunto tras implementar; los que caigan
por usar un grupo interno propio se corrigen para dar `base.group_user`.

## Casos (RED), `tests/unit/base/test_res_users_share_field.py`

1. `share` es columna almacenada con `compute='_compute_share'`.
2. Interno por clausura: un grupo que implica `base.group_user` da
   `share=False`.
3. Añadir y retirar `base.group_user` (desde el grupo) recalcula en base.
4. Buscable: `search([('share', '=', False)])` trae al interno y no al
   externo.
5. Cambiar la implicación de un grupo recalcula.
6. Un grupo `user_type='internal'` que no es `base.group_user` **no** hace
   interno (la regla es literal).

## Anulaciones previstas

- `all_group_ids` → `group_ids` en el cómputo: cae el 2 (y el 5).
- quitar `store=True`: cae el 4.
- volver a `user_type`: cae el 6.

## Addendum — implementación y anulaciones (2026-11-25)

- El aviso al lado inverso **sí** hacía falta para un reverso de Django; se
  implementó en `_notify_m2m_modified` (ver el addendum de
  `orm-m2m-modified-inverse-side-0356.md`). Anulación B1: sin él caen los casos
  2, 3 y 4 de esta unidad; los cuatro de `test_orm` sobreviven.
- Anulación B2 (`group_ids` en lugar de `all_group_ids`): caen el 2 y el 5.
- El caso 4 filtra por la columna con el manager: `res.users` es un modelo de
  Django y no tiene `search`; la columna es lo que hace buscable al campo.
- Migración `0129_res_users_share.py`: `makemigrations --check` limpio
  (`editable=False`, como todo calculado almacenado).
- Tests ajenos corregidos a `base.group_user` (decisión 1), medidos por el
  subconjunto de consumidores de `share` (19 archivos):
  `test_res_users_user_type.py::test_interno`,
  `test_digest_signals.py::test_subscribes_internal_user_on_create` y el
  helper `_user` de `test_res_partner_user_and_lang.py`.

## Símbolos nuevos, su referencia y su prueba

| Símbolo | Referencia | Prueba |
|---|---|---|
| `src/orm/models.py: _notify_inverse_side` | `odoo19c: odoo/orm/fields_relational.py:1586-1593` | `tests/unit/base/test_res_users_share_field.py` (casos 2-4 desde el grupo), `tests/unit/orm/test_m2m_modified_inverse_side.py` |
| `src/addons/base/migrations/0129_res_users_share.py` (`0129_res_users_share`) | `odoo19c: odoo/addons/base/models/res_users.py:234-235,459-464` | `tests/unit/base/test_res_users_share_field.py::test_share_is_a_stored_compute` |
| `ResUsers._compute_share` | `odoo19c: odoo/addons/base/models/res_users.py:459-464` | `tests/unit/base/test_res_users_share_field.py` |
