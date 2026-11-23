# U5 — `return.request` adopta `BaseModel` con borrado lógico

Fecha: 2026-11-23T20:53:46. TASK-API-0397, unidad hija de `basemodel-adoption-0397`.
Partición: `outputs/stock-basemodel-adoption-research.md`, sección 6, fila U5.

`return.request` es un modelo propio del L0: la referencia no lo tiene, así
que no hay contraparte que citar. Lo que gobierna su borrado es
**DEC-DOC-007** (`docs: source/gestion/decisiones/index.rst`): «cuando se
hace un delete es un delete lógico»; `ReturnRequest` está en su lista.

El mecanismo del borrado sí es de la referencia:
`odoo19c: odoo/orm/models.py:4203-4209` (`check_access('unlink')` y los
`_ondelete_methods` antes de borrar), que `BaseModel.unlink` ya porta.

## El conflicto que la unidad resuelve

`BaseModel.unlink` borra con `AccessQuerySet(model=type(self))`: un
`DELETE` físico. En un modelo con `SoftDeleteModel` eso contradice
DEC-DOC-007. La instancia sigue teniendo `delete()` lógico (el de
`SoftDeleteModel` queda antes que el de Django en el MRO), pero
`record.unlink()` —la forma de la fuente— borraría la fila.

## Qué cambia

1. `BaseModel.unlink` toma el QuerySet del borrado de un gancho de clase,
   `_unlink_queryset`, que por defecto devuelve el `AccessQuerySet` de
   siempre. Las guardas, el `modified(before=True)` y la invalidación no
   cambian.
2. `SoftDeleteModel._unlink_queryset` devuelve `SoftDeleteQuerySet`, cuyo
   `delete()` es el `UPDATE is_deleted = true` que DEC-DOC-007 fija. Un
   `unlink` sobre el recordset conserva la fila; `hard_delete()` sigue
   siendo el borrado físico.
3. `ReturnRequest` hereda `BaseModel`, con `SoftDeleteModel` **primero** en
   las bases: el gancho se resuelve por el MRO, y con `BaseModel` delante su
   `_unlink_queryset` por defecto gana y el borrado vuelve a ser físico
   (medido: la prueba nueva cae con ese orden). Sus hijos (`ReturnItem`,
   `ReturnHistoryEntry`, `ReturnEvidence`) no declaran `_name` y siguen
   como modelos de Django: sus reversos (`items`, `history_entries`,
   `evidence`) siguen siendo gestores.

**Divergencia declarada:** la fuente no tiene borrado lógico; su archivado es
`active` y `unlink` siempre borra. Aquí el borrado lógico es una decisión
del proyecto (DEC-DOC-007), y el gancho es el punto donde se aplica.

Prueba: `tests/integration/stock/test_soft_delete_returnrequest.py` — el
`unlink` del recordset marca la fila y la oculta del gestor por defecto.
Anulación, restaurada con `cmp`: retirar `SoftDeleteModel._unlink_queryset`
tumba sólo `test_unlink_on_the_recordset_is_logical`.

Símbolos tocados: `BaseModel.unlink` y `BaseModel._unlink_queryset`
(`src/orm/models.py`), `SoftDeleteModel._unlink_queryset`
(`src/addons/base/models/soft_delete_mixin.py`), `ReturnRequest`
(`addons/stock/models/return_request.py`). `BaseModel.unlink` es un
mecanismo transversal: su cobertura es el gate completo, y la rama por
defecto devuelve el mismo `AccessQuerySet` que antes.

## Lo que este corte no cierra

La búsqueda de `BaseModel` filtra filas archivadas por `active`/`x_active`
(`active_test`), no por `is_deleted`: un `search` sobre un modelo con
borrado lógico devolvería filas borradas. Sucesor:
`soft-delete-active-test-0397`.
