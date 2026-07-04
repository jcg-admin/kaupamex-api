---
name: kanban-flow-metrics
description: "Use when measuring and evaluating Kanban system flow. kanban:flow-metrics — measure cycle time, lead time, throughput and WIP, build the Cumulative Flow Diagram, detect bottlenecks and forecast delivery with percentile-based Service Level Expectations."
allowed-tools: Read Glob Grep Bash Write Edit
effort: medium
disable-model-invocation: true
metadata:
  triggers: ["cycle time", "lead time", "throughput", "cumulative flow diagram", "service level expectation", "Little's Law", "flow metrics"]
updated_at: 2026-06-02
---

# /kanban-flow-metrics — Kanban: Flow Metrics

> *"You can't improve what you don't measure — but in flow systems, the average lies. Measure the distribution, forecast with percentiles, and let the Cumulative Flow Diagram show you where the work is stuck."*

Mide el flujo del sistema Kanban con datos reales: **cycle time, lead time, throughput y WIP**. Construye el **Cumulative Flow Diagram (CFD)**, identifica cuellos de botella y variabilidad, y predice entregas con percentiles para comunicar un **Service Level Expectation (SLE)** a los stakeholders. La métrica gobierna sobre la opinión.

**THYROX Stage:** Stage 11 TRACK-EVALUATE.

**Outputs clave:** Cumulative Flow Diagram · cycle time / lead time (percentiles 50/85/95) · throughput · Service Level Expectation (SLE).

---

## Pre-condición

Requiere:
- Tablero Kanban operativo con columnas (estados) definidas y WIP limits aplicados.
- Marcas de tiempo (timestamps) por transición de columna instrumentadas — sin ellas no hay métrica posible.
- Al menos 2-4 semanas de datos de tránsito real para que las distribuciones tengan sentido.

---

## Cuándo usar este paso

- Cuando el tablero Kanban lleva semanas operando y se necesita evaluar el flujo con datos.
- Cuando los stakeholders piden un compromiso de entrega ("¿cuándo estará listo?") y se quiere responder con un percentil, no con una corazonada.
- Cuando se sospecha un cuello de botella pero falta evidencia para localizarlo.

## Cuándo NO usar este paso

- Sin timestamps por columna — las métricas serían estimaciones inventadas, prohibidas por el quality gate.
- Con menos de ~2 semanas de datos — la distribución no es representativa y los percentiles engañan.
- Para fijar metas de productividad individual — las flow metrics miden el sistema, no a las personas.

---

## Las cuatro métricas de flujo

| Métrica | Definición | Unidad | Para qué sirve |
|---------|-----------|--------|----------------|
| **Cycle time** | Tiempo desde que el ítem entra a *In Progress* hasta que llega a *Done* | días | Predecir cuánto tarda el trabajo ya comprometido |
| **Lead time** | Tiempo desde que el ítem entra a la cola (*commitment point*) hasta *Done* | días | Lo que percibe el cliente: la promesa end-to-end |
| **Throughput** | Número de ítems completados por unidad de tiempo | ítems/semana | Capacidad de entrega del sistema |
| **WIP** | Ítems en curso simultáneamente entre commitment y delivery | ítems | Carga del sistema; insumo de Little's Law |

**Little's Law** relaciona las tres: `Lead Time ≈ WIP / Throughput`. Reducir el WIP (a throughput constante) reduce el lead time. Es la justificación matemática de los WIP limits y la palanca central del flujo.

---

## Actividades

| Actividad | Output | Técnica clave |
|-----------|--------|---------------|
| **1. Instrumentar timestamps** | Registro de entrada/salida por columna para cada ítem | Captura por transición de estado; un par `(columna, timestamp)` por movimiento |
| **2. Calcular percentiles** | Cycle/lead time p50, p85, p95 | Ordenar la muestra; percentil, NO promedio (la distribución es asimétrica con cola larga) |
| **3. Medir throughput** | Ítems/semana en una ventana móvil | Conteo de transiciones a *Done* por periodo |
| **4. Construir el CFD** | Cumulative Flow Diagram | Conteo acumulado de ítems por estado a lo largo del tiempo (bandas apiladas) |
| **5. Verificar Little's Law** | Consistencia WIP / throughput / lead time | Comparar lead time medido vs `WIP / Throughput` esperado |
| **6. Definir el SLE** | "El X% de los ítems se entrega en ≤ N días" | Tomar el percentil acordado (p. ej. p85) como compromiso comunicable |

---

## Cumulative Flow Diagram (CFD) — cómo se lee

El CFD apila el conteo acumulado de ítems en cada estado contra el tiempo. Cada banda es una columna del tablero.

| Señal en el CFD | Interpretación |
|-----------------|----------------|
| **Banda que se ensancha** | El estado acumula trabajo más rápido de lo que lo libera → **cuello de botella** |
| **Distancia vertical entre curvas** | WIP aproximado en ese instante |
| **Distancia horizontal entre curvas** | Lead/cycle time aproximado |
| **Bandas paralelas y estables** | Flujo equilibrado: entrada ≈ salida |
| **Banda plana arriba (arrival)** | Replenishment detenido — la cola no se alimenta |
| **Banda plana abajo (departure)** | Entregas detenidas — nada llega a *Done* |

La regla práctica: **la banda que crece es el cuello**. El ancho de banda en el tiempo es la deuda de flujo acumulada en ese estado.

---

## Percentiles, no promedios

El cycle time de un sistema Kanban es una distribución asimétrica con cola larga: unos pocos ítems tardan mucho más que la mediana. El promedio queda contaminado por esa cola y subestima el riesgo.

- **p50 (mediana):** la mitad de los ítems termina en ≤ este tiempo. Útil como expectativa central.
- **p85:** valor recomendado para el SLE — equilibrio entre realismo y compromiso.
- **p95:** cubre casi todo; útil para SLAs estrictos y para dimensionar el peor caso razonable.

El SLE se comunica como frase verificable: *"El 85% de las solicitudes estándar se completa en 12 días o menos"*. Es un pronóstico probabilístico basado en datos históricos, no una promesa determinista.

---

## Criterio de completitud — ¿flujo medido y comunicado?

**Medición completa (todos los siguientes):**
1. CFD generado con datos reales de timestamps por columna.
2. Cycle time y lead time reportados con p50/p85/p95 (no promedios).
3. Throughput calculado sobre una ventana móvil reciente.
4. Little's Law verificada — lead time medido coherente con `WIP / Throughput`.
5. Al menos un cuello de botella localizado (o confirmación de que no hay banda ensanchándose).
6. SLE definido y comunicado a los stakeholders.

**Requiere más medición:**
- Las métricas provienen de estimaciones y no de timestamps reales → instrumentar primero.
- Se reportaron promedios en lugar de percentiles → recalcular.
- El SLE no se comunicó o no es verificable contra datos → reformular.

---

## Artefacto esperado

`{wp}/kanban-flow-metrics.md`

Contiene: CFD (o referencia al gráfico), tabla de percentiles por clase de servicio, throughput de la ventana, verificación de Little's Law, cuellos identificados y el SLE comprometido.

---

## Red Flags — señales de medición mal ejecutada

- **Métricas basadas en estimaciones** — si los números salen de "lo que el equipo cree que tarda" y no de timestamps registrados, no son métricas: son opiniones disfrazadas de datos.
- **Reportar promedios** — el promedio de cycle time oculta la cola larga y produce SLEs que se incumplen sistemáticamente; usar siempre percentiles.
- **CFD con bandas que se cruzan** — si las curvas acumuladas se cruzan, el conteo está mal calculado (un acumulado nunca decrece).
- **SLE no comunicado** — medir el flujo sin convertirlo en una expectativa que los stakeholders puedan usar deja el análisis sin efecto práctico.
- **Ignorar el cuello visible** — detectar la banda que se ensancha y no actuar es desperdiciar la medición; el cuello gobierna el throughput de todo el sistema.
- **Forecast determinista** — prometer una fecha exacta a partir de una distribución es ignorar la variabilidad; el compromiso es probabilístico (percentil + nivel de confianza).

---

## Integración con otros namespaces

- **`lean:`** — cycle time y throughput son métricas Lean de flujo; un cuello en el CFD equivale a una restricción de flujo (Theory of Constraints). El `lean-measure` aporta el baseline cuantitativo y `lean-improve` ataca el cuello detectado aquí.
- **`dmaic-measure`** — la captura de timestamps y la validación de la muestra alimentan el sistema de medición; los percentiles de cycle time son la `Y` del proceso a estabilizar.
- **`dmaic-control`** — el SLE y el throughput se vigilan con control estadístico (control charts de cycle time) para detectar variación especial vs común.
- **`pm-monitoring`** — el SLE y el CFD son insumos del control de avance del proyecto; complementan (no reemplazan) el EVM con una vista de flujo real.
- **Ciclo THYROX** — Stage 11 TRACK-EVALUATE consume las flow metrics para decidir si el sistema entrega de forma predecible; los hallazgos retroalimentan Stage 8 PLAN EXECUTION (replenishment y clases de servicio) y Stage 12 STANDARDIZE.

---

## Estado en now.md

**Al INICIAR este step:**
```yaml
methodology_step: kanban:flow-metrics
flow: kanban
thyrox_stage: 11-track-evaluate
```

**Al COMPLETAR** (flujo medido y SLE comunicado):
```yaml
methodology_step: kanban:flow-metrics  # completado → SLE vigente
flow: kanban
thyrox_stage: 11-track-evaluate
```

## Siguiente paso

- Flujo medido, cuello localizado → `kanban:queue-management` para repriorizar y ajustar replenishment, o `lean:improve` para atacar el cuello.
- SLE estable y predecible → `thyrox:standardize` (Stage 12) para fijar el sistema de medición como estándar.

---

## Limitaciones

- Las flow metrics describen el comportamiento histórico del sistema; el forecast por percentiles asume que el futuro se parece al pasado — cambios estructurales (nuevo equipo, nuevo tipo de trabajo) invalidan el SLE hasta recolectar datos nuevos.
- El CFD muestra *dónde* se acumula el trabajo pero no *por qué*; localizar el cuello no lo resuelve — requiere análisis de causa raíz (Lean / DMAIC).
- Little's Law se cumple en promedio sobre sistemas estables; en sistemas con WIP muy variable o con ítems abandonados, la relación `WIP / Throughput` es solo una aproximación.

---

## Reference Files

Este skill no requiere assets ni references adicionales: las fórmulas (percentiles, Little's Law) y la construcción del CFD están descritas en línea. Si el WP genera scripts de cálculo, ubicarlos en `scripts/` siguiendo la anatomía oficial.
