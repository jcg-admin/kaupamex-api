# Calibración de benchmarks y umbrales

> COSMIC da **tamaño** (CFP); convertir a **esfuerzo** o a **umbral de atomicidad**
> requiere calibración con datos del propio proyecto. **No extrapoles entre capas.**

## Qué calibrar

1. **CFP promedio por banda** (Small/Medium/Large) por capa, a partir de procesos medidos.
2. **Umbral de atomicidad** (CFP máximo de un proceso implementable en una unidad de trabajo).
3. **Productividad** (horas/CFP) si se estima esfuerzo — con histórico propio.

## Procedimiento

1. Mide N procesos representativos de la capa (método estándar, movimiento a movimiento).
2. Calcula media/distribución → fija bandas y umbral con evidencia.
3. Documenta el alcance: el umbral **vale solo para esa capa**.

## Esfuerzo: incluir retrabajo y trabajo no-funcional (MM v5.0 Parte 2 §3)

> **Regla (no negociable) — el esfuerzo de calibración NO se calcula solo con las
> corridas "limpias".** Excluir los fallos/retrabajo o el trabajo de 0 CFP infla
> la productividad y subestima toda estimación posterior.

El Measurement Manual v5.0 (Parte 2, §3, líneas 749-771) es explícito:

- Un cambio de software proviene de (a) **nuevo FUR**, (b) **cambio de FUR**, o
  (c) **corrección de defecto**. *"Las reglas para el tamaño… son las mismas pero
  el medidor se [pone en] alerta para **distinguir las diversas circunstancias
  cuando se hacen mediciones de rendimiento y estimaciones**"* (L749-751).
- *"El tamaño funcional… **no cambia** si el software debe ser cambiado para
  corregir un defecto"* (L768-771) → **la corrección de defecto = 0 CFP pero
  esfuerzo real.**

**Corolario para productividad (size/effort, MM Parte 2 L326):**

1. Calcula **DOS** tasas, no una:
   - **Tasa new-FUR "limpia"** = ΣCFP nuevos / Σ esfuerzo de procesos sin
     defecto ni retrabajo. Es el **mejor caso** (optimista).
   - **Tasa all-in** = ΣCFP entregados / Σ **TODO** el esfuerzo de la capa,
     incluyendo: (a) corrección de defectos/retrabajo (0 CFP), (b) trabajo
     no-funcional (atributos nuevos, campos calculados, anotaciones de schema,
     hardening — 0 CFP, ver `estimation.md` NFR), (c) reconciliación por fallo
     de agente/herramienta.
2. **Para ESTIMAR el backlog usa la tasa all-in**, no la limpia. La limpia solo
   sirve para entender el techo teórico.
3. Reporta el **% de esfuerzo a 0 CFP** (trabajo no-funcional + defectos). Si es
   alto (en kaupamex: ~41% del wall-clock api del loop), una estimación basada
   solo en CFP nuevos subestima ~⅓.
4. **Agrega, no cherry-pick** (MM Parte 2 §4.2, ágil L801-808; guía completa:
   [manual/guideline-agile-cosmic-trudel-buglione.md](manual/guideline-agile-cosmic-trudel-buglione.md),
   Trudel & Buglione IWSM/MetriKon 2010): la correlación CFP↔esfuerzo es buena
   **agregando** los tamaños de las US/procesos de la iteración (y los USP de
   Fibonacci **no son una medida**), no eligiendo las corridas limpias.

**Fuente de datos del esfuerzo:** debe ser trazable (en kaupamex: `duration_ms`
de los subagentes + overhead de reconciliación del orquestador). Marca lo que NO
puedas medir (p. ej. la reconciliación orquestada no está en `duration_ms` → la
tasa all-in es un **piso**, no el valor exacto).

**Anti-patrón (ERR-15):** excluir el agente que falló ("unreliable") de la
calibración. Eso contradice L749-751 (distinguir, no descartar) y produce una
tasa optimista. El defecto es esfuerzo real con 0 CFP → entra en la tasa all-in.

## Precedente kaupamex (NO copiar valores — calibrar los tuyos)

- Umbral atomicidad capa **api = 8 CFP** (calibrado con UC-INV-02 = 7 CFP, UC-AUTH-02 = 8 CFP).
- Decisión explícita de **no extrapolar** ese umbral a ui/db/server (DEC-COSMIC-002/006).
- Benchmarks **calibrados** preferidos sobre los genéricos de industria (DEC-COSMIC-003).

---
**Última actualización:** 2026-06-03T09:23:02Z (añadida la regla de esfuerzo
all-in: incluir retrabajo/defectos + trabajo no-funcional; MM v5.0 Parte 2 §3).
