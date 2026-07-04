---
name: kanban-queue-management
description: "Use when managing the Kanban input queue — prioritizing by cost of delay / WSJF, triaging requests, assigning classes of service and defining a cadenced replenishment policy. kanban:queue-management — minimize lead time of the highest-value work by deciding what enters the system and in what order."
allowed-tools: Read Glob Grep Bash Write Edit
effort: medium
disable-model-invocation: true
metadata:
  triggers: ["cost of delay", "WSJF", "replenishment", "classes of service", "queue prioritization", "triage", "input queue"]
updated_at: 2026-06-02
---

# /kanban-queue-management — Kanban: Queue Management

> *"The queue is where economics happen. Most of an item's lead time is spent waiting, not working — so the highest-leverage decision in flow is not how fast you build, but what you let into the system and in what order. FIFO is fair; cost of delay is profitable."*

Gestiona la **cola de entrada** del sistema Kanban: decide qué trabajo entra, en qué orden y bajo qué política. Prioriza por **cost of delay** (no FIFO ciego), hace **triage** de las solicitudes, asigna **classes of service** (expedite, fixed date, standard, intangible) y define una **política de replenishment** cadenciada. El objetivo es minimizar el lead time del trabajo de mayor valor: el sistema solo puede entregar lo que entra, y el orden de entrada gobierna lo que el cliente percibe.

**THYROX Stage:** Stage 8 PLAN EXECUTION / Stage 11 TRACK-EVALUATE.

**Outputs clave:** cola priorizada · classes of service asignadas · política de replenishment.

---

## Pre-condición

Requiere:
- Tablero Kanban operativo con commitment point definido (`kanban-board-setup`) — la cola vive *antes* de ese punto.
- WIP limits aplicados aguas abajo — sin ellos, la cola no se gobierna porque cualquier cosa entra de inmediato.
- Backlog de solicitudes con suficiente información para estimar valor y urgencia (no necesariamente tamaño exacto).

---

## Cuándo usar este paso

- Cuando hay más demanda que capacidad y se necesita decidir qué entra primero con criterio económico.
- Cuando el equipo jala trabajo en orden FIFO o por "el que grita más fuerte" y el trabajo de alto valor espera detrás de trivialidades.
- Cuando la cola de entrada crece sin control y nadie decide cuándo ni cuánto reabastecer (replenishment).
- Cuando aparecen urgencias frecuentes que rompen el flujo sin una clase de servicio que las encauce.

## Cuándo NO usar este paso

- Sin commitment point claro — si no se sabe dónde el equipo se compromete con un ítem, no hay frontera de cola que gestionar.
- Para microgestionar el orden tarea a tarea cada hora — el replenishment es cadenciado, no continuo; reordenar constantemente es ruido.
- Como sustituto del análisis de valor del producto — la cola prioriza lo que ya se decidió construir; el *qué construir* es trabajo aguas arriba.

---

## Priorización por cost of delay — no FIFO ciego

El **cost of delay (CoD)** es el costo económico de no tener un ítem terminado por unidad de tiempo: cuánto se pierde (o se deja de ganar) por cada semana de retraso. Priorizar por CoD ordena la cola por impacto económico, no por orden de llegada.

Cuando se conoce el CoD y una estimación del tamaño, el orden óptimo es **WSJF (Weighted Shortest Job First)**:

```
WSJF = Cost of Delay / Job Duration (tamaño)
```

Se jala primero el ítem con mayor WSJF: alto valor y corto. Esto minimiza el cost of delay total acumulado de toda la cola — es el resultado del *scheduling* económico, no una heurística arbitraria.

Para estimar el CoD sin cifras monetarias exactas, descomponerlo en tres componentes (estilo SAFe) y puntuarlos en escala relativa:

| Componente del CoD | Pregunta | Ejemplo |
|--------------------|----------|---------|
| **User/business value** | ¿Cuánto valor entrega al usuario o al negocio? | Feature de pago que desbloquea ingresos |
| **Time criticality** | ¿El valor decae con el tiempo? ¿Hay una ventana? | Promoción estacional, fecha legal |
| **Risk reduction / opportunity** | ¿Reduce riesgo o abre oportunidades futuras? | Spike que destraba una integración crítica |

`CoD ≈ value + time-criticality + risk/opportunity`. Luego `WSJF = CoD / tamaño`.

La regla práctica: **lo valioso y corto va primero; lo costoso de retrasar no espera detrás de lo barato de retrasar.**

---

## Classes of service — encauzar tipos de urgencia distintos

No todo el trabajo tiene el mismo perfil de cost of delay. Las **classes of service** asignan a cada ítem una política de selección y flujo según *cómo* crece su costo de retraso en el tiempo:

| Clase | Perfil de cost of delay | Política de cola |
|-------|-------------------------|------------------|
| **Expedite** | CoD muy alto e inmediato (pérdida en curso) | Se jala de inmediato; carril propio; rompe WIP si hace falta — **límite 1 a la vez** |
| **Fixed date** | CoD bajo hasta la fecha, luego salta | Se planifica hacia atrás desde la fecha; entra a tiempo para cumplir el SLE |
| **Standard** | CoD lineal y moderado | Orden por WSJF dentro de su prioridad; el grueso del flujo |
| **Intangible** | CoD bajo ahora, alto a futuro (deuda) | Capacidad reservada fija para que no sea desplazada siempre |

El **carril expedite tiene límite 1**: si todo es urgente, nada lo es, y un carril expedite sin tope reproduce el caos que pretendía resolver. La clase intangible (deuda técnica, refactor) necesita **capacidad reservada** porque su CoD inmediato bajo la hace perder siempre contra lo urgente — sin reserva, nunca se hace.

---

## Replenishment — reabastecer con cadencia, no por goteo

El **replenishment** es el acto de mover ítems desde el backlog (orden de ideas) a la cola comprometida (commitment point) donde el equipo se obliga a entregarlos. La política responde a tres preguntas:

| Pregunta | Decisión |
|----------|----------|
| **¿Cuándo?** | En una **cadencia** fija (replenishment meeting semanal o quincenal), no cada vez que se libera un hueco |
| **¿Cuánto?** | Hasta llenar la cola hasta su límite — ni más (infla el lead time) ni menos (deja capacidad ociosa) |
| **¿Qué?** | Los ítems de mayor WSJF disponibles, respetando las reservas por clase de servicio |

La cadencia desacopla el *commitment* de la *capacidad instantánea*: el equipo se compromete con un lote priorizado en cada meeting, en lugar de jalar reactivamente lo que esté arriba del backlog. **El commitment es tardío y reversible mientras el ítem está en el backlog; una vez cruzado el commitment point, el reloj del lead time corre.**

Regla práctica: **comprometerse lo más tarde posible** (last responsible moment) y solo con lo que el sistema puede absorber sin inflar la cola.

---

## Actividades

| Actividad | Output | Técnica clave |
|-----------|--------|---------------|
| **1. Triage de solicitudes** | Backlog filtrado (aceptado / rechazado / pendiente de info) | Descartar lo que no aporta valor antes de priorizar; no priorizar ruido |
| **2. Estimar cost of delay** | CoD relativo por ítem | Value + time-criticality + risk/opportunity en escala relativa |
| **3. Ordenar por WSJF** | Cola priorizada | `CoD / tamaño`; mayor WSJF primero |
| **4. Asignar class of service** | Clase por ítem | Expedite / fixed-date / standard / intangible según perfil de CoD |
| **5. Definir replenishment** | Política cadenciada (cuándo/cuánto/qué) | Meeting con cadencia fija + reservas por clase |
| **6. Revisar en cadencia** | Cola re-priorizada cada ciclo | Re-evaluar WSJF; el valor y la urgencia cambian con el tiempo |

---

## Criterio de completitud — ¿Cola gobernada?

**Cola gobernada (todos los siguientes):**
1. Triage hecho — solo entra a la cola lo que aporta valor; el ruido se descartó o devolvió.
2. Cola ordenada por WSJF (o cost of delay relativo), no por orden de llegada.
3. Cada ítem comprometido tiene una class of service asignada.
4. Carril expedite con límite explícito (1 a la vez) y clase intangible con capacidad reservada.
5. Política de replenishment definida: cadencia, cantidad y criterio de selección.
6. La cola se revisa en cada cadencia — la priorización es viva, no un orden fijado una vez.

**Requiere más iteración:**
- La cola sigue siendo FIFO o "el que grita más fuerte" — falta criterio económico.
- El carril expedite no tiene límite — todo termina siendo urgente.
- El replenishment es reactivo (goteo continuo) en lugar de cadenciado.
- La clase intangible nunca se ejecuta — falta reservar capacidad.

---

## Artefacto esperado

`{wp}/plan-execution/kanban-queue.md`

Contiene: backlog triado, tabla de priorización por WSJF (CoD + tamaño), class of service por ítem, política de replenishment (cadencia/cantidad/reservas) y las reglas del carril expedite.

---

## Red Flags — señales de cola mal gestionada

- **FIFO ciego** — la cola se jala en orden de llegada; el trabajo de alto cost of delay espera detrás de trivialidades baratas de retrasar.
- **Priorización por volumen de voz** — el orden lo fija quién insiste más, no el valor económico; síntoma de ausencia de cost of delay.
- **Expedite sin límite** — todo se marca "urgente"; el carril expedite deja de significar nada y rompe el flujo permanentemente.
- **Intangible perpetuamente desplazado** — la deuda técnica nunca entra porque su CoD inmediato es bajo; sin capacidad reservada, el sistema acumula deuda hasta degradarse.
- **Replenishment por goteo** — se jala del backlog cada vez que se libera un hueco, sin cadencia; el commitment se vuelve reactivo y la cola se infla.
- **Cola fijada una sola vez** — se prioriza al inicio y nunca se revisa; el WSJF cambia con el tiempo y un orden viejo es un orden equivocado.
- **Tamaño confundido con valor** — se prioriza lo grande "porque cuesta más"; WSJF favorece lo valioso *y corto*, no lo grande.

---

## Integración con otros namespaces

- **`lean:` (flujo, throughput):** la cola de entrada es el punto donde se controla la sobreproducción (waste Lean): no admitir más trabajo del que el sistema puede absorber preserva el throughput. Priorizar por cost of delay alinea el flujo con el valor, que es el primer principio Lean. El `lean-improve` que ataca un cuello reduce el tamaño efectivo de los ítems y cambia el WSJF.
- **`dmaic-measure`:** el cost of delay y el WSJF necesitan datos — tamaño (de las flow metrics) y valor/urgencia estimados; `dmaic-measure` aporta el sistema de medición que vuelve la priorización defendible en lugar de subjetiva.
- **`dmaic-control`:** la cadencia de replenishment y los límites por clase de servicio son controles del proceso; vigilar que la cola no se infle y que el carril expedite no exceda su límite es control estadístico aplicado a la admisión de trabajo.
- **`pm-monitoring`:** la cola priorizada y las clases de servicio alimentan el control de avance del proyecto — qué se comprometió, en qué orden y con qué SLE; complementan el seguimiento de scope/cronograma con una vista de admisión por valor.
- **`kanban-flow-metrics`:** simbiosis directa — el tamaño y el lead time medidos allí son insumo del WSJF y del SLE por clase de servicio aquí; a su vez, una cola bien gobernada estabiliza las distribuciones que `kanban-flow-metrics` reporta (Stage 11 retroalimenta Stage 8).
- **Ciclo THYROX:** la cola se diseña y opera en Stage 8 PLAN EXECUTION (qué entra al sistema y cómo) y se re-evalúa en Stage 11 TRACK-EVALUATE (la priorización es viva: el cost of delay cambia y el replenishment se ajusta con los datos de flujo).

---

## Estado en now.md

**Al INICIAR este step:**
```yaml
methodology_step: kanban:queue-management
flow: kanban
thyrox_stage: 8-plan-execution
```

**Al COMPLETAR** (cola gobernada y replenishment cadenciado):
```yaml
methodology_step: kanban:queue-management  # completado → cola priorizada vigente
flow: kanban
thyrox_stage: 8-plan-execution
```

## Siguiente paso

- Cola priorizada y replenishment definido → `kanban:flow-metrics` (Stage 11) para medir si el orden elegido entrega el valor esperado y ajustar el SLE por clase de servicio.
- Cuello aguas abajo que distorsiona la cola → `lean:improve` para atacar la restricción antes de seguir admitiendo trabajo.

---

## Limitaciones

- El WSJF depende de estimaciones de cost of delay y tamaño; si esas estimaciones son groseras, el orden que produce es solo aproximado — su valor está en forzar la conversación económica, no en una precisión falsa.
- Priorizar por cost of delay optimiza el valor entregado pero puede dejar ítems de bajo CoD permanentemente al fondo (starvation); las reservas por clase de servicio mitigan esto, no lo eliminan.
- La cola gestiona el orden de admisión, no la velocidad de entrega: una cola perfecta sobre un sistema con cuello de botella sigue entregando lento — la priorización complementa la mejora de flujo (`lean:` / `kanban-flow-metrics`), no la reemplaza.

---

## Reference Files

Este skill no requiere assets ni references adicionales: las fórmulas (cost of delay, WSJF) y las políticas (classes of service, replenishment cadenciado) están descritas en línea. Si el WP genera plantillas de priorización o scripts de cálculo de WSJF, ubicarlos en `assets/` o `scripts/` siguiendo la anatomía oficial.
