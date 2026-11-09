# Porte completo de `odoo/tools/sql.py` → `src/tools/sql.py`

Directiva del ejecutor 2026-11-09: *«implementar en kaupamex-api TODO lo que
existe en odoo/tools/sql.py»*. Referencia: odoo-tools
`abe4040ec1a45beee90fb694e4eae4453e46b389` (781 líneas).

## Censo medido (AST de los dos archivos, nivel de módulo y métodos de clase)

- Referencia: 55 símbolos. Nuestro: 58. Ausente por nombre: **`__all__`**.
- Extras nuestros: `SQL.resolve_expression`, `execute_sql`,
  `sql_order_by_type`, `SQL_ORDER_BY_TYPE_UNKNOWN`.
- Obligaciones abiertas del inventario (`obligation_classification.tsv`,
  TASK-API-0486): `SQL.__init__` (`structural=signature`), `SQL.__slots__`
  (`value`), `SQL.__code`, `SQL.__params`, `SQL.__to_flush` (`unresolved`),
  y el archivo (`mirror=yes`). El resto de los símbolos ya no figura abierto.

## Divergencias que se cierran

| Pieza | Referencia | Nuestro | Decisión |
|---|---|---|---|
| `__all__` | 8 nombres (`:22-31`) | ausente | se porta verbatim |
| anotaciones de `SQL` | `__code: str`, `__params: tuple`, `__to_flush: tuple[Field, ...]` (`:82-84`) | ausentes | se portan; `Field` sólo como cadena (`from __future__ import annotations` ya rige la referencia) |
| `SQL.__slots__` | `('__code', '__params', '__to_flush')` | + `'__output_field'` | se retira el slot extra |
| `SQL.__init__` | `(code="", /, *args, to_flush=None, **kwargs)` | + `output_field=None` | se retira el parámetro |
| `SQL.resolve_expression` | no existe | adaptación Django | se retira de `SQL`; su único productor, `stock_quant._read_group_select`, que ya mezcla `Sum` de Django, devuelve `RawSQL(…, output_field=DecimalField())` |
| `SQL_ORDER_BY_TYPE` | `defaultdict(lambda: 16, {...})` (`:261`) | `dict` + `sql_order_by_type` + `SQL_ORDER_BY_TYPE_UNKNOWN` | `defaultdict` verbatim; `Field.column_order` lee el mapa como la referencia (`fields.py:1092`); se retiran la función y la constante |

`execute_sql` se queda: no tiene contraparte porque el cursor de la referencia
cuelga del `Environment` y aquí es `connections[alias]`; su docstring declara
el ciclo de importación que lo obliga. No contradice nada de la referencia.

Medido antes de decidir: `SQL` usado como expresión de Django (`annotate`,
`aggregate`, `filter`, `Q(SQL(`…) → 0 usos estáticos fuera de
`stock_quant`; la suite completa es la prueba dinámica.

## Pruebas

`tests/unit/tools/test_sql_reference_shape.py`, marcada `reference`. Lee la
referencia **por AST**, sin ejecutarla ni importarla, y compara con el módulo
nuestro:

1. `__all__` igual;
2. `SQL.__slots__` igual;
3. la firma de `SQL.__init__`: mismos parámetros, mismos tipos y valores por
   defecto;
4. las anotaciones de clase de `SQL` (sus nombres);
5. `SQL_ORDER_BY_TYPE` con la misma tabla y el mismo valor por defecto para
   un tipo desconocido.

El contrato sale de la referencia, no de una lista escrita en la prueba.

Las pruebas de la adaptación en `tests/unit/tools/test_sql.py`
(`output_field`/`resolve_expression`) se retiran con ella. La de
`stock_quant` pasa a verificar el `RawSQL` del consumidor.
