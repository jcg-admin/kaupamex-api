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

## Derivación completa (ampliación por directiva del ejecutor)

**Revisión:** odoo-tools `abe4040ec1a45beee90fb694e4eae4453e46b389`,
`odoo/tools/sql.py`. Confirmado sobre la fuente antes de modificar nada:
`def __init__(self, code: (str | SQL) = "", /, *args, to_flush: (Field |
Iterable[Field] | None) = None, **kwargs)` (`:87`); `__slots__ = ('__code',
'__params', '__to_flush')` (`:80`); anotaciones `__code: str`,
`__params: tuple`, `__to_flush: tuple[Field, ...]` (`:82-84`).

**Comportamiento exigido de `SQL`** (`:46-201`): copia desde otro `SQL` sin
más argumentos; rechazo de posicionales y nombrados a la vez; nombrados →
`named_to_positional_printf`; sin argumentos, `code % ()` valida que no haya
`%s`; composición de argumentos `SQL` (código, parámetros y `to_flush` de cada
parte); `code`, `params` (lista), `to_flush` (propio y de las partes);
`__repr__`, `__bool__`, `__eq__`, `__hash__`, `__iter__`, `join`,
`identifier`.

**Consumidores de `to_flush`:** `Environment.execute_query`
(`odoo/orm/environments.py:517` ≙ `src/orm/environments.py:1410`) y
`BaseModel._read_group_*` (`odoo/orm/models.py:3912` ≙
`src/orm/models.py:7947`). Ninguno usa `output_field` ni `resolve_expression`.

**Implementación Django existente:** mismo cuerpo que la referencia más la
adaptación `output_field` + `resolve_expression`, introducida al retirar el
alias `SQL = RawSQL` (H-API-698) para que `stock_quant._read_group_select`
siguiera devolviendo una expresión de Django.

**Adaptación legítima que se conserva:** `execute_sql` — ejecuta un `SQL` con
el cursor `connections[alias]`. No se presenta como símbolo portado; su
docstring declara el ciclo `orm.environments` ↔ `tools.query` que lo obliga.
Consumidores: `src/orm/environments.py`, `src/tools/query.py`.

**Alternativas descartadas:**

- Conservar `output_field` en `SQL`: añade un parámetro y un slot que la
  referencia no tiene, con un único productor. La justificación es una
  conveniencia del consumidor, no una necesidad del contrato.
- Subclase `DjangoSQL(SQL)` con `output_field`: segunda clase para un único
  uso; `RawSQL` de Django ya es exactamente eso.
- Dejar `SQL_ORDER_BY_TYPE` como `dict`: la función auxiliar evita que una
  lectura añada la clave, pero la referencia sí la añade y su consumidor
  (`Field.column_order`, `fields.py:1092`) lee el mapa directamente.

**Consumidores afectados:** `addons/stock/models/stock_quant.py`
(`_read_group_select`, 2 llamadas) y `src/orm/fields.py`
(`column_order` vía `sql_order_by_type`).

**Pruebas funcionales que se conservan:** todo `tests/unit/tools/test_sql.py`
salvo los tres casos de la adaptación retirada; `test_sql_column_schema.py`,
`test_sql_schema_helpers.py`, `tests/unit/orm/test_field_conversion.py`
(orden de columnas). Se añade a `test_sql.py` el caso que discrimina el
`defaultdict`: un tipo desconocido ordena con 16 y queda en el mapa.

**Controles de anulación:** restaurar `output_field` en la firma tumba la
prueba de firma y la de slots; quitar `__all__` tumba la suya; volver al
`dict` llano tumba la de la tabla y la funcional del tipo desconocido.

**Regresiones:** subconjunto derivado de
`grep -rlE "tools.sql|tools import sql|from tools.sql|SQL_ORDER_BY_TYPE|column_order|_read_group_select" tests/`,
y suite completa y multidb sobre la revisión.

**Criterio de settlement:** RED de las cinco pruebas de forma y de la
funcional del `defaultdict`, GREEN, controles, regresión de impacto, suite
completa sin fallos nuevos, multidb `pytest_exit 0`, árbol limpio y
`verify=0` de `settle_item`. Las cinco pruebas de forma no bastan solas.
