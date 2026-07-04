```yml
type: Principio de Proyecto
category: Flujo de trabajo — diseño-primero (RUP) y make html opcional
version: 1.0.0
created_at: 2026-06-03T15:27:49
applies_to: e-comerce v1.0.0+
origen: directiva ejecutor 2026-06-03 ("el objetivo está en que los UCs estén
  definidos correctamente en requisitos/ y diseñados por RUP en
  arquitectura-tecnica/, y de ahí se pasa a implementación; make html opcional")
```

# Flujo de trabajo — diseño-primero (RUP) · `make html` opcional

> Cargado automáticamente en cada sesión (I-009). Aplica a TODA feature
> nueva o cambio funcional. Refuerza y secuencia `principio-rector-rup-arquitectura.md`.

## 1. `make html` (docs) es OPCIONAL y lento — NO es un gate del loop

**NO correr `make html` como paso bloqueante** dentro del loop de trabajo.
Es lento (rebuild completo del árbol Sphinx ~15-20 min, sin Java para
PlantUML) e involucra deuda pre-existente ajena al cambio (warnings/errores
RST heredados — ver US-3.13).

Correr `make html` **solo** cuando:

- El ejecutor lo pide explícitamente, **o**
- Hay sospecha fundada de error de **sintaxis RST nueva** introducida por el
  cambio (nueva directiva, toctree, list-table grande).

Para validar RST de un archivo puntual sin el build completo, usar un parse
rápido (docutils) en vez de `make html`. El DoD del commit **no** incluye
`make html` (ya documentado en `test-execution-protocol.md` y el CLAUDE.md de
docs; esta regla lo refuerza tras gastar tiempo en builds innecesarios).

## 2. Secuencia canónica: docs (diseño) → código (implementación)

El objetivo del trabajo en `docs/` es que cada caso de uso esté **bien
definido** y **bien diseñado** ANTES de implementarlo. Orden obligatorio:

```
1. UC bien DEFINIDO    → source/requisitos/**        (casos-uso + requisitos-funcionales)
2. DISEÑADO por RUP     → source/arquitectura-tecnica/**  (vistas Kruchten, módulos, modelos)
3. IMPLEMENTACIÓN       → server → db → api → ui
```

- **Diseño-primero, no code-first.** Las features del loop Fase-1 se hicieron
  code-first (api/ui primero, docs/8-capas backfilled) — eso generó la deuda
  documental de 8 capas que hubo que cerrar después. Para lo nuevo: **definir
  el UC + diseñarlo en `arquitectura-tecnica/` primero**, luego implementar.
- Esto es la fase **Elaboration antes que Construction** de RUP, y subsume
  el "ANALYZE/DISCOVER antes de ejecutar" del principio rector + I-001.
- El diseño en `arquitectura-tecnica/` sigue los **skills RUP** del proyecto
  (vistas 4+1 de Kruchten, modelos, módulos) — no es un volcado libre.

## 3. Implicación para el orden de capas en implementación

Cuando un UC ya está definido + diseñado, la implementación baja por capas
de infraestructura hacia arriba: **server** (provisioning si aplica) → **db**
(schema/objetos) → **api** (modelos/endpoints/tests TDD) → **ui** (vistas).
No todas las features tocan las 4; pero el orden relativo se respeta cuando sí.

## 4. Qué NO cambia

- La verificación de las **8 capas** (Clausula 4 del principio rector) sigue
  siendo obligatoria al cerrar — esta regla la **secuencia** (diseño antes que
  código), no la reemplaza.
- Los gates de código (DB-socket+pytest TDD para api; Node v20+jest+lazy+canon
  para ui) siguen siendo obligatorios y SÍ bloquean el commit. Lo único
  degradado a opcional es `make html`.

## Severidad

**MEDIA** — sin esta regla se reincide en (a) gastar tiempo en `make html`
innecesario y (b) construir code-first y acumular deuda documental de 8 capas
para backfill posterior. Con ella, el diseño RUP precede a la implementación.
