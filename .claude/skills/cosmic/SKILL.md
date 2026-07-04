```yml
name: cosmic
description: "Dimensionamiento funcional COSMIC v5.0 (ISO/IEC 19761) en CFP. Usar cuando se quiera medir el tamaño funcional de software desde sus FUR/casos de uso: mapear procesos funcionales y sus movimientos de datos (Entrada/Salida/Lectura/Escritura), estimar tamaño temprano cuando falta detalle, o calibrar benchmarks de esfuerzo. Encaja en la fase MEASURE/BASELINE."
allowed-tools: Read Glob Grep Bash
```

# COSMIC — Dimensionamiento funcional (ISO/IEC 19761, v5.0)

**Motor de medición de tamaño funcional.** Mide el software en **CFP** (COSMIC Function
Points) a partir de sus **Functional User Requirements (FUR)**. Independiente de
tecnología, lenguaje y esfuerzo. Encaja en **MEASURE/BASELINE** (Stage 2).

> Fuente autoritativa: el Measurement Manual v5.0 y guías en
> [references/manual/](references/manual/README.md). Citarlo para toda regla.

## Modelo en una frase

Un **proceso funcional** (iniciado por **un** evento desencadenante detectado por un
**usuario funcional**) se compone de **movimientos de datos**. Hay **4 tipos, 1 CFP cada
uno**: **Entrada (E)**, **Salida (X)**, **Lectura (R)**, **Escritura (W)**. Tamaño del
proceso = nº de movimientos. Tamaño total = Σ procesos dentro del scope (una sola capa).

## Procedimiento (las 3 fases COSMIC)

### Fase A — Measurement Strategy
Definir y registrar (usar `assets/measurement-strategy.md.template`):
- **Propósito** de la medición y **scope**.
- **Usuarios funcionales** y la **boundary**.
- **Capa/FSM**: por **Principio 6**, una medición se limita a **UNA capa** (UI, API, DB,
  server son capas separadas → mediciones independientes). Ver [references/layers.md](references/layers.md).
- **Nivel de granularidad** consistente (no mezclar niveles de descomposición).

### Fase B — Mapping
De los **FUR** (fuente exclusiva — Regla 3; en THYROX: casos de uso / requirements-spec del WP):
1. Identificar **procesos funcionales** — uno por **evento desencadenante** único (P-GSM-6).
2. Identificar **data groups** — uno por **object of interest**.
3. Identificar los **movimientos de datos** de cada proceso (E/X/R/W).
   Guía operativa + casos límite (navegación/cómputo = 0 CFP): [references/data-movements.md](references/data-movements.md).
4. Excluir NFR (no cuentan CFP).
> Patrón para derivar movimientos desde casos de uso (paso a paso del flujo): ver el paper
> [manual/llm-automation-cosmic-from-usecases.md](references/manual/llm-automation-cosmic-from-usecases.md).

### Fase C — Measurement
- Tamaño del proceso = nº de movimientos (P-GSM-8). **Mínimo 2 CFP** (Regla 10c: 1 Entrada
  + 1 Salida o Escritura).
- Un (tipo, data group) se cuenta **una vez por proceso funcional**.
- Registrar en la tabla **COSMIC Format** (`assets/cosmic-format-table.md.template`):
  columnas `Paso · Sub-proceso (FUR) · FU · OOI · Tipo(E/X/R/W) · CFP · FUR-fuente` + total.
- Tamaño total = Σ procesos por capa.

## Cuando falta detalle → estimación temprana

Si los FUR no tienen granularidad para identificar cada movimiento, **no fuerces** una
medición parcial: usa **early sizing** (Average FP, Equal-size bands, analogía) y marca
`[ESTIMACIÓN TEMPRANA]`. Técnicas y cuándo usar cada una: [references/estimation.md](references/estimation.md).

## Benchmarks y calibración

Para convertir CFP en esfuerzo/atomicidad, **calibra por capa con tus propios datos** — no
extrapoles umbrales entre capas. Genéricos vs calibrados: [references/calibration.md](references/calibration.md).

## No-intrusión

La anotación COSMIC se añade como **sección al final** del UC/FUR, **sin modificar** sus
partes existentes. Garantiza trazabilidad y re-medición sin reescribir.

## Reglas que nunca se violan (del MM v5.0)

- 1 movimiento de datos mueve **un único** grupo de datos = 1 CFP.
- Cada proceso funcional tiene **≥1 Entrada** (la del evento desencadenante).
- **Mínimo 2 CFP** por proceso funcional (Regla 10c).
- Medir **una capa por FSM** (Principio 6); comparar solo dentro del mismo nivel.
- FUR son la **fuente exclusiva** del tamaño (Regla 3).
- Las cifras CFP se respaldan con la fuente (caso de uso / código) — claims OBSERVABLE (I-012).

## Salidas

- `measurement-strategy.md` (Fase A) · tabla COSMIC Format por proceso (Fase C) · total CFP
  por capa + resumen. Viven en el WP (`measure/` o anotados en el UC).

## Referencias

- [references/manual/](references/manual/README.md) — Manual oficial v5.0 (Partes 1-3) + guías + paper LLM.
- [references/data-movements.md](references/data-movements.md) · [references/layers.md](references/layers.md) ·
  [references/estimation.md](references/estimation.md) · [references/calibration.md](references/calibration.md)
