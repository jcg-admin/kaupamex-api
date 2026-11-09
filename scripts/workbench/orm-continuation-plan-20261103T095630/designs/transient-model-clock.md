# Modelo transitorio: reloj de la transacción y acceso — diseño

Fecha: 2026-11-09T04:56:15

**Referencia.** `odoo-tools@abe4040ec1a45beee90fb694e4eae4453e46b389`, Odoo 19 Community,
`odoo/orm/models_transient.py` (completo), `odoo/orm/model_classes.py:217-220`.

## Contrato derivado del código ejecutable

| Cláusula | Referencia | Kaupamex antes |
|---|---|---|
| todo transitorio tiene columnas de acceso | `model_classes.py:217-220` (TypeError sin `_log_access`) | `created_at`/`updated_at` declarados en `TransientModel` |
| valor de esas columnas | `cr.now()` (`models.py:4801-4805`, `:4394-4396`) | `DateTimeField(auto_now…)`, reloj de pared |
| corte del barrido | `self.env.cr.now() - seconds`, piso 300 s (`models_transient.py:75-79`) | `timezone.now()` |
| borrado | `self.sudo().search(domain, limit=GC_UNLINK_LIMIT).unlink()` | `objects.filter(pk__in=…).delete()` |
| acceso «sólo los propios» del docstring | **no hay implementación**: sin regla `create_uid` en `ir_rule.py`, sin caso transitorio en `ir_model` (sólo reflexión `:434,488`) | docstring lo declara «no portado» |

## Decisión

- Las columnas del transitorio usan `TransactionDateTimeField` con el mismo encuadre de guardado
  de `TimeStampedModel` (una lectura por `save`, alias de escritura). `deconstruct` es
  `DateTimeField`: sin migración.
- El corte usa `transaction_now` sobre el alias del modelo.
- El docstring se corrige: la referencia no ejecuta la restricción por creador.
- El borrado por `delete()` frente a `unlink()` queda fuera: es otra cláusula, que se mide aparte.

## Pruebas discriminantes

- Las fechas del alta de un transitorio igualan `transaction_now`.
- Con el reloj de pared adelantado un día (`timezone.now` sustituido), una fila recién escrita
  sobrevive al barrido: sólo el reloj de la transacción la protege.

## Propietario del reloj

`transaction_now`, `TransactionDateTimeField` y el encuadre de guardado pasan de
`addons/base/models/timestamped_mixin.py` a `src/orm/fields_temporal.py`: el reloj es
del ORM (≙ `Cursor.now()`), y `src/orm` no importa de `addons`. `timestamped_mixin`
los reexporta en `__all__`; sus importadores no cambian. Las pruebas que sustituyen el
reloj apuntan ahora a `orm.fields_temporal`, que es donde el campo lo busca.

## Verificación

- RED: `red/transient-model-clock.txt` (2 casos).
- Focal y consumidores directos (79 casos): pasan. `makemigrations --check`: sin cambios.
- Controles: con el corte por `timezone.now()` cae sólo el del reloj de pared adelantado;
  con `DateTimeField` de Django cae sólo el de las fechas del alta.
