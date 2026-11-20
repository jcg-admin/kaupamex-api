# res.users._default_groups — el default de group_ids

Unidad `res-users-default-groups-0485`. Destapada por la etapa 1 del
cluster de variantes: con `product.product` en `BaseModel` la ACL se aplica,
y un usuario creado sin grupos no puede leer el catálogo
(`tests/integration/test_v2_cart_wishlist_notifications.py::TestWishlistCartTransfersV2::test_move_to_cart_returns_200`
→ 403 sobre `product.ProductProduct`).

## Referencia

- `odoo19c: odoo/addons/base/models/res_users.py:203-212` — `_default_groups`:
  `base.group_user` más los `implied_ids` de `base.default_user_group`.
- `odoo19c: odoo/addons/base/models/res_users.py:257` — `group_ids` con
  `default=lambda s: s._default_groups()`: se aplica cuando `create` no trae
  `group_ids` en `vals`.

## Prosa heredada que se corrige

`src/addons/base/models/res_users.py` declaraba `_default_groups` en la
divergencia «capa de vista de su cliente OWL». Es falso: es el `default`
de un campo, no un diálogo con el cliente. Se retira de esa lista y se porta.

## Diseño

- `ResUsers._default_groups(self)` en `src/addons/base/models/res_users.py`,
  mismo cuerpo que la fuente (por `IrModelData.ref`).
- `ResUsersManager._create_user`: si `group_ids is None` (no viene en
  `vals`), aplica `self.model._default_groups()`. Una lista explícita, vacía
  incluida, se respeta como en la fuente.

## Pruebas

`tests/unit/base/test_res_users_default_groups.py`: un usuario creado sin
grupos queda en `base.group_user` (y los implicados de
`base.default_user_group`); uno creado con `group_ids` explícitos conserva
sólo esos. Anulación: sin el default, cae exactamente el primer caso.

## Radio

Todo usuario creado sin grupos pasa a interno. Suite completa obligatoria.
