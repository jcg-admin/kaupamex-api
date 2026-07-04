# Identificar movimientos de datos (E / X / R / W)

> Operativa para la Fase B (Mapping). Reglas autoritativas: [manual/part1-principles-rules.md](manual/part1-principles-rules.md), [manual/part3-rules.md](manual/part3-rules.md).

Cada movimiento mueve **un único grupo de datos** (un object of interest) y vale **1 CFP**.
La manipulación/cálculo asociada va **incluida** en el movimiento (no se cuenta aparte).

| Tipo | Mueve un data group… | Pista en un caso de uso |
|------|----------------------|--------------------------|
| **Entrada (E)** | de un usuario funcional → al proceso (cruza boundary) | el actor envía/solicita datos; el **trigger** es siempre una Entrada |
| **Salida (X)** | del proceso → a un usuario funcional | el sistema muestra/devuelve datos al actor |
| **Lectura (R)** | de almacenamiento persistente → al proceso | el sistema consulta/recupera de la BD |
| **Escritura (W)** | del proceso → a almacenamiento persistente | el sistema guarda/actualiza/borra en la BD |

## Conteo

- Un (tipo, data group) se cuenta **una vez por proceso funcional** (movimientos idénticos repetidos no se duplican).
- Cada proceso tiene **≥1 Entrada** y **mínimo 2 CFP** (Regla 10c).

## NO son movimientos de datos (0 CFP)

- Navegación entre pantallas sin transferir datos del OOI.
- Cálculo/validación puros (van incluidos en un movimiento existente).
- Re-mostrar datos ya movidos en el mismo proceso.
- Mensajes de control sin datos de un OOI de los FUR.

> Casos límite (mensajes de error/confirmación, datos de control): resolver con
> [manual/part3-rules.md](manual/part3-rules.md) y [manual/part2-guidelines.md](manual/part2-guidelines.md).

---
**Última actualización:** 2026-06-03T03:44:23Z
