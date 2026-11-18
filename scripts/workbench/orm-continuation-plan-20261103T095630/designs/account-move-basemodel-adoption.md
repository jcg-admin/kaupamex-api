# `account.move` adopta `BaseModel` (paso C3)

Unidad: `orm-fk-delete-policy-contract-0515`, paso C3 de
`restrict-ondelete-partial-reconcile.md`. Revisión de partida: `e60f5b88`.

## Fuente

`odoo19c: addons/account/models/account_move.py:4055` — `unlink`:

```
self._update_sequence_made_gap(invalidate_current=True)
self = self.with_context(skip_invoice_sync=True, dynamic_unlink=True)
logger_message = self._get_unlink_logger_message()
self.line_ids.remove_move_reconcile()
self.line_ids.unlink()
res = super().unlink()
```

`unlink` es de `BaseModel`: para portarlo el modelo tiene que serlo.

## Medición de la adopción sola

Con sólo cambiar la base a `class AccountMove(models.BaseModel,
SequenceMixin)` (sin migración: `makemigrations --check` no detecta
cambios), la regresión derivada de 14 directorios da **46 fallos y 2
errores sobre 5691 que pasan**. Cuatro clases, contadas por su línea `E`:

| Clase | Casos | Causa |
|---|---|---|
| `'AccountMoveLine' object has no attribute 'aggregate'` / `'filter'` / `'all'` / `'count'` / `'model'` | 44 | `move.line_ids` pasa de gestor de Django a recordset, porque sus dos extremos ya son `BaseModel` |
| `PermissionDenied: … consultar registros de «Journal Entry»` | 3 | pruebas sin usuario ni `sudo` que leen `line.move.state`; un `BaseModel` comprueba el acceso de lectura |
| `('draft',) == ('cancel',)` | 1 | `test_migration_0039_fills_the_existing_lines` cambia el estado con `QuerySet.update` y la operación lee la caché del registro |

Los 44 salen de 17 sitios de código en 10 archivos (los demás son
llamadas que pasan por ellos, sobre todo por `is_balanced`):

| Archivo | Sitios | Forma |
|---|---|---|
| `addons/account/models/account_move.py` | 5 | `aggregate` ×3, `filter(...).values_list`, `exists` |
| `addons/account/wizard/account_move_reversal.py` | 4 | `all` ×2, `filter(account__account_type__in=…)` ×2 |
| `addons/account/wizard/account_automatic_entry_wizard.py` | 3 | `filter(account=…)` |
| `addons/account_debit_note/wizard/account_debit_note.py` | 2 | `.model`, `all` |
| `addons/account/wizard/account_payment_register.py` | 1 | `filter(…).first()` |
| `addons/account/wizard/account_validate_account_move.py` | 1 | `exists` |
| `addons/account/services.py` | 1 | `all` |
| `addons/account_fleet/models/account_move.py` | 1 | `all` |

`chart_template.py` y `account_bank_statement.py` aparecen en la búsqueda
por texto y no cuentan: su `line_ids` es de otro modelo.

## Cambio

1. **La base.** `class AccountMove(models.BaseModel, SequenceMixin)`.
2. **Los 17 sitios** pasan a la forma de recordset, que es la de la
   fuente:

   | Antes | Después |
   |---|---|
   | `line_ids.all()` | `line_ids` |
   | `line_ids.exists()` | `line_ids` en contexto booleano |
   | `line_ids.model` | `type(line_ids)` no hace falta: se crea con `line_ids.create` sobre el recordset vacío del modelo |
   | `line_ids.filter(account=x)` | `line_ids.filtered(lambda line: line.account_id == x.pk)` |
   | `line_ids.filter(account__account_type__in=t)` | `line_ids.filtered(lambda line: line.account and line.account.account_type in t)` |
   | `line_ids.aggregate(Sum(campo))` | `sum(line_ids.mapped(campo), Decimal('0'))` |

   El orden de las líneas pasa de `Meta.ordering` (`move`, `id`) al
   `_order` del apunte (`date desc, move_name desc, id`); dentro de un
   asiento las dos claves primeras son constantes, así que el orden sigue
   siendo por `id`. Los sitios que emparejan líneas con `zip` dependen de
   eso.
3. **`unlink`** con el orden de la fuente: `remove_move_reconcile`,
   `line_ids.unlink()`, `super().unlink()`. Quedan `pendiente:` con su
   línea `_update_sequence_made_gap` (`:4056`; `made_sequence_gap` no está
   portado), el contexto `skip_invoice_sync`/`dynamic_unlink` (`:4057`; no
   hay sincronización dinámica de líneas) y `_get_unlink_logger_message`
   (`:4058`). Los dos `@api.ondelete` (`:4024`, `:4044`) tampoco entran:
   son reglas de quién puede borrar, no del contrato de borrado de FK;
   quedan declarados en el método.
4. **Pruebas.** Las tres sin contexto reciben el `sudo` de sus hermanas;
   la de la migración 0039 invalida la caché tras su `update`, que es lo
   que una migración real tiene (ninguna caché previa). Las pruebas que
   usan `move.line_ids` como gestor se convierten con la misma tabla.

## Pruebas del contrato

`tests/unit/account/test_reconcile_delete_contract.py`, clase
`TestMoveUnlink`:

| Caso | Espera |
|---|---|
| `move.unlink()` con una línea conciliada | asiento, líneas y parcial desaparecen; el apunte del otro asiento queda con `matching_number` vacío |
| `move.unlink()` de un asiento sin conciliar | asiento y líneas desaparecen |
| `unlink()` del conjunto vacío | `True` |

Anulación: sin `self.line_ids.remove_move_reconcile()` y sin
`self.line_ids.unlink()` cae el primero (el parcial desaparece por
`CASCADE`, pero nadie recalcula el otro apunte).

## Límite

Si tras convertir los 17 sitios la regresión derivada deja fallos de una
clase nueva —en particular de acceso en una ruta HTTP, que sería un cambio
de contrato del producto y no una conversión—, se detiene, se registra y C4
no se aplica.

*Métrica:* resumen de pytest de la regresión derivada (14 directorios,
`-n 4`, sin `test_multidb_isolation`) y sus líneas `E` agrupadas.
*Ciega a:* un lector de `move.line_ids` fuera de esos directorios; la F2
completa lo cubre al cerrar el bloque.
