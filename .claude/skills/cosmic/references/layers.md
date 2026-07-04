# Capas y boundary (Principio 6)

> Una medición FSM se limita a **UNA sola capa**. Capas distintas = mediciones
> independientes y **no comparables** entre sí salvo al mismo nivel de descomposición.

## Identificar capas

Ejemplos de capas separadas en un stack típico:

| Capa | Usuario funcional típico | Boundary |
|------|--------------------------|----------|
| **UI** (p.ej. React) | persona (usuario final) | UI ↔ persona / UI ↔ API |
| **API** (p.ej. Django/Node) | la UI u otro software; gateways externos (pago) | API ↔ UI / API ↔ servicio externo |
| **DB** | la API | DB ↔ API |
| **server/infra** | operador / otros servicios | según el caso |

## Reglas

- Mide cada capa por separado; **no mezcles** capas en la misma tabla/total.
- Define los **usuarios funcionales por capa** (cambian: para la API, la UI es un usuario funcional).
- Un mismo evento de negocio puede generar procesos funcionales en varias capas
  (UI + API + DB) — se miden por separado.

> Precedente: e-comerce midió 4 capas (api/ui/db/server) con umbrales propios
> (DEC-COSMIC-001 / DEC-COSMIC-006). Identifica TUS capas, no copies las suyas.

---
**Última actualización:** 2026-06-03T03:44:23Z
