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

## Resultado: límite alcanzado, C3 detenido (2026-11-18T03:20Z)

Con la base cambiada, los 17 sitios convertidos, `unlink` portado y los
ajustes de prueba, la misma regresión derivada da **46 fallos sobre 5696
que pasan** (`boot_id 55781402…`, tras el segundo reclamo). La clase del
gestor casi desaparece y aparece la que el límite nombraba:

| Clase | Líneas `E` | Qué es |
|---|---|---|
| `PermissionDenied … «Journal Item» (account.AccountMoveLine)` | 35 | `move.line_ids` ya es un recordset y leer sus campos comprueba el acceso de lectura del usuario del entorno |
| `PermissionDenied … «Journal Entry» (account.AccountMove)` | 3 | lectura de `line.move` sin usuario |
| `assert 403 == 201` / `assert 403 == 409` | 4 | **ruta HTTP** `POST /api/v2/admin/finance/invoices/<id>/register-payment/` |
| `'AccountMoveLine' object has no attribute 'all'` / `'count'` | 4 | pruebas que usan `move.line_ids` como gestor; conversión pendiente, mecánica |

La tercera fila decide. El usuario de
`tests/integration/account/test_register_payment_endpoint.py` tiene la
capacidad del producto que gobierna esa ruta y no pertenece a ningún grupo
contable de la fuente. Antes la ruta leía las líneas por el gestor de
Django, sin regla de acceso; con `account.move` como `BaseModel` la
lectura pasa por `check_access` (`src/orm/models.py`, vía `mapped` desde
`AccountMove.is_balanced`) y la ruta responde 403. Lo mismo alcanza a
`tests/integration/company/test_subscription_ledger.py` (5 casos), que
publica una factura de suscripción.

Eso no es una conversión de sitio: es decidir cómo se relacionan las
**capacidades** del producto (`HasCapability`, DEC-11) con los **grupos**
de la fuente que gobiernan `ir.model.access` cuando un modelo contable
pasa por el ORM. Hay al menos tres salidas y ninguna la elige este
contrato:

1. el servicio de la ruta corre con `sudo()` tras la comprobación de
   capacidad (la capacidad es la autorización; el ORM no vuelve a
   preguntar);
2. cada capacidad contable otorga el grupo de la fuente equivalente;
3. `account.move` no adopta `BaseModel` hasta que exista esa
   correspondencia para todo el dominio contable.

**Decisión pendiente de otra autoridad** (el ejecutor: toca DEC-11 y el
contrato de las rutas `/api/v2/admin/finance/`). Hasta tenerla:

- C3 no se publica. El trabajo se conserva como parche aplicable sobre
  `0ecbe3f0`: `outputs/orm-fk-delete-policy-contract-0515/
  c3-account-move-adoption.patch` (10 archivos, 91 inserciones, 40
  borrados; `git apply --check` pasa). La lista de los 46 fallos está en
  `c3-regression-failures.txt`, junto a él.
- C4 no se aplica: sin `AccountMove.unlink`, `PROTECT` convertiría en
  error el borrado de un asiento conciliado, que la fuente permite.
- Las dos filas de `account.AccountPartialReconcile` siguen `xfail` y la
  unidad `orm-fk-delete-policy-contract-0515` no se asienta.

Condición de cierre: una decisión registrada sobre capacidades y grupos
para el dominio contable; con ella se aplica el parche, se convierten las
cuatro pruebas de la última fila, se dan usuario o `sudo` a las pruebas
unitarias sin contexto y se continúa con C4.

Lo que sí queda publicado y verificado del bloque: C1, C2a, la lectura
multi-registro del ORM y C2. `line.unlink()` ya deshace la conciliación.

*Métrica:* líneas `E` y resumen de pytest de la regresión derivada.
*Ciega a:* otras rutas HTTP contables sin prueba de integración, que
tendrían el mismo 403 sin que esta medición lo vea.
