# Unidad 6d — `regex_field_agg` y `read_group` (obsoleto en 19.0)

Autoridad: `odoo19c: odoo/orm/models.py:112` (`regex_field_agg`) y
`:2746-2878` (`read_group`), odoo-tools
`abe4040ec1a45beee90fb694e4eae4453e46b389`.

## Contrato medido

`read_group(domain, fields, groupby, offset=0, limit=None, orderby=False,
lazy=True)` — decorado `@api.model`, `@api.readonly` y
`@api.deprecated("Since 19.0, read_group is deprecated. …")`:

1. `groupby` texto → lista; `lazy` agrupa sólo por el primero.
2. Cada spec se valida (campo inexistente → `ValueError`; propiedad sobre
   campo no `properties` → `ValueError`); fecha sin granularidad → `:month`.
3. Agregados: `<campo>_count` en modo lazy con un solo grupo, `__count` si
   no; `fields` admite `campo`, `campo:func` y `nombre:func(campo)`
   (`regex_field_agg`); un campo almacenado con columna y `aggregator`
   que no es a la vez el grupo toma su agregador por defecto.
4. `orderby` se reescribe a los specs anotados; sin él, el orden es el de
   los grupos.
5. `_read_group` → filas como dicts; `fill_temporal` del contexto →
   `_read_group_fill_temporal`; lazy → `_read_group_fill_results`.
6. Cada fila recibe `__domain` (el dominio de entrada) y, si quedan grupos,
   `__context = {'group_by': resto}`; `_read_group_format_result` cierra.

## Lo que se reutiliza

`_read_group`, `_read_group_fill_temporal`, `_read_group_fill_results`,
`_read_group_format_result` (unidades 5, 6a-6c), `parse_read_group_spec`,
`api.readonly`, `api.deprecated` (`warnings.deprecated`),
`Field.base_field`, `Field.column_type`, `Field.aggregator`.

## Consumidor que sigue bloqueado — su reclamo cambia

`AccountInvoiceReport._read_group_select` decía que `read_group` no existe
en `src/orm`. Tras esta unidad existe, pero en `BaseModel`, y
`account.invoice.report` es un `models.Model` de Django (medido:
`issubclass(models.Model, BaseModel)` → `False`): su `super()` sigue sin
base. El mensaje y el docstring se corrigen en el mismo pase; el sucesor
#473 se conserva.

## Casos (`tests/unit/orm/test_read_group_public.py`, `test_orm.message`)

1. lazy por many2one → `discussion`, `discussion_count`, agregado por
   defecto de `priority`, `__domain` como lista;
2. `nombre:func(campo)` y `campo:func`;
3. eager con dos grupos → `__count` y sin `__context`; lazy con dos →
   `__context`;
4. campo inexistente → `ValueError`;
5. `orderby` por agregado anotado;
6. `fill_temporal` del contexto rellena meses (`test_orm.mixed`);
7. emite `DeprecationWarning`.

Anulación prevista: retirar el agregador por defecto (cae 1) y retirar la
llamada a `_read_group_fill_temporal` (cae 6).
