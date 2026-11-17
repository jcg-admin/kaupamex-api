# Frontera Decimal/UoM y política de verificación proporcional

Fecha: 2026-11-17. Revisión de partida: `61f390f8`. Referencia: `odoo19c@abe4040ec1`.

## Política de selección de pruebas (instrucción 4.2.0)

| Nivel | Qué cubre | Cuándo |
|---|---|---|
| F0 | sintaxis, estilo, pruebas enfocadas, RED/GREEN y anulación | todo cambio |
| F1 | regresión derivada sobre los consumidores del grafo | todo cambio con consumidores |
| F2 | suite completa | revisión de integración estable o cambio transversal |
| F3 | ci-multidb y migraciones | sólo si cambia routing, Environment, Registry, caché, transacciones, ComputeStoredFields, migraciones, seeds o provisión |

El subconjunto F1 se deriva con
`grep -rlE "<símbolos>" --include=*.py tests/ | sed 's|/[^/]*$||' | sort | uniq -c`
y el comando se cita junto al resultado. La evidencia sólo se reutiliza ligada a
la misma revisión y alcance.

## Contrato de la referencia (`addons/uom/models/uom_uom.py:147-203`)

- `_compute_quantity(qty, to_unit, round=True, rounding_method='UP',
  raise_if_failure=True)`: `if not self or not qty: return qty`, luego
  `self.ensure_one()`. Misma unidad devuelve `qty`; distinta, `qty * factor /
  to_unit.factor`; redondea a `to_unit.rounding` sólo si hay destino y `round`.
- `raise_if_failure` se declara y **no se usa** en el cuerpo de 19: no hay
  chequeo de categoría (la 19 ya no tiene `uom.category`). Dos unidades sin raíz
  común se convierten por factor absoluto sin error. Se porta igual.
- `_compute_price`: `self.ensure_one()` **antes** de la guarda, así que un
  recordset vacío levanta.

## Diferencias locales medidas

1. Falta la guarda `not self` y `ensure_one()` en `_compute_quantity`.
2. Falta el parámetro `raise_if_failure`.
3. Falta `ensure_one()` en `_compute_price`.
4. Un `Decimal` de entrada levanta `TypeError` (`Decimal * float`) en todos los
   caminos que tocan `factor` o `float_round`.

## Decisión: conversión que conserva el tipo

`float` entra → `float` sale (sin cambio para ningún consumidor que hoy
funciona). `Decimal` entra → el cálculo pasa por `float` (`float_round` es
puerto verbatim de un algoritmo de coma flotante; ver `_as_float`) y el
resultado vuelve como `Decimal(repr(resultado))`. Ningún consumidor actual
pasa un `Decimal` con éxito, porque hoy ese camino levanta: el cambio no altera
ningún resultado vigente y habilita a los que ya convierten a mano.

Descartado: todo-float (obliga a cada consumidor `Decimal` a convertir dos
veces y pierde el tipo del campo) y Decimal universal (cambiaría el tipo de
retorno para los consumidores float de stock, que suman sobre `float`).

## Controles

misma unidad, unidades distintas, cero, negativo, fracción, redondeo, raíces
distintas, recordset vacío, recordset múltiple, `raise_if_failure`, y tipo
`Decimal`/`float`, para cantidad y precio.

## Recordset vacío y múltiple: no aplican a `Uom` (medido)

`Uom` hereda de `TimeStampedModel` → `models.Model`, no de `BaseModel`: medido
en una sonda, la instancia no tiene `ensure_one`, ni `browse`, ni `__len__`, y
`bool(instancia)` es `True`. Una instancia de Django es siempre exactamente un
registro, y la unidad vacía de un Many2one local es `None`, que no tiene
métodos. Por eso `if not self` y `self.ensure_one()` son invariantes de la
representación, no código por portar: un recordset vacío o múltiple de
`uom.uom` no se puede construir. Si `Uom` migra a `BaseModel` (sucesor del
inventario ORM), estas dos guardas pasan a ser obligatorias y sus controles
se reabren. El control que sí aplica es `to_unit=None` (`if to_unit:`).

## Precisión de Decimal → float → Decimal (medida 2026-11-17)

Sonda en Python puro, 200 000 valores aleatorios por clase, escala 4:

| Dígitos significativos | Fallos de ida y vuelta |
|---|---|
| 12, 13, 14, 15 | 0 |
| 16 | 18 164 (ej. `904417079281.3122` → `…3123`, error 0.0001) |

- La columna `(16, 4)` admite 16 dígitos: un valor con `|qty| ≥ 1e11` puede
  perder el último decimal. La fuente tiene el mismo límite, porque allí la
  cantidad es `float` de punta a punta; el porte no lo empeora, y no lo
  mejora. Queda como límite declarado, no como defecto a corregir aquí.
- Con `round=False` el resultado puede traer ruido binario más allá de la
  escala de la columna (`0.1 × 3` → `Decimal('0.30000000000000004')`), igual
  que el `float` de la fuente. Con `round=True` (el valor por defecto) el
  resultado sale redondeado a `to_unit.rounding`.

*Métrica:* igualdad `Decimal(repr(float(d))) == d`.
*Ciega a:* la acumulación de error en una cadena de conversiones sucesivas
sin redondeo intermedio.

## F1 (2026-11-17)

Subconjunto derivado con
`grep -rlE "_compute_quantity|_compute_price|check_qty|addons\.uom|from addons.uom" --include=*.py tests/ | sed 's|/[^/]*$||' | sort | uniq -c`
(12 directorios): `6644 passed, 39 skipped, 81 xfailed` en 806.96 s con
`-n 4`. Anulación de `_like`: caen exactamente las 8 pruebas de tipo `Decimal`
y sobreviven las 5 de `float`, cero y raíces distintas.

## Primitivas de recordset en `Uom`: obligaciones NO verificadas

`if not self` y `ensure_one()` no se pueden ejercitar sobre una instancia de
Django. Eso no demuestra que sean equivalentes. Quedan como obligación no
verificada hasta que `Uom` gane las primitivas de recordset o se demuestre la
equivalencia contractual (investigación en curso, a registrar en `outputs/`).
