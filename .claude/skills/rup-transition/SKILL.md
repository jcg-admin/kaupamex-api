---
name: rup-transition
description: "Use when deploying the system to end users in RUP. rup:transition — deploy to production, conduct user acceptance, resolve critical defects, reach PD milestone for formal product release."
allowed-tools: Read Glob Grep Bash Write Edit
effort: medium
disable-model-invocation: true
metadata:
  triggers: ["RUP transition", "PD milestone", "product release RUP", "UAT user acceptance", "beta deployment"]
updated_at: 2026-05-21 03:19:20
---

# /rup-transition — RUP: Transition

> **Adaptacion kaupamex v2 (2026-05-21).** En kaupamex el estado y
> la coordinacion intra-sesion **persisten en ``docs/source/``**, en
> los `.rst` de la iniciativa. Las salidas de Transition NO viven en
> `{wp}/rup-transition.md` sino mapeadas asi sobre los artefactos
> de ``docs/source/gestion/pm/<submodulo>/iniciativas/<slug>/``:
>
> - **Plan de deployment** -> ``tareas-<slug>.rst`` con T-NNN de
>   deployment + iniciativas hermanas en submodulo ``server`` si el
>   despliegue requiere infra (apache config, dns, certs).
> - **UAT plan + results** -> ``progreso-<slug>.rst`` seccion
>   "UAT iter N" con criterios + resultados; defects encontrados
>   en seccion "Defectos UAT".
> - **Defect log post-beta** -> ``progreso-<slug>.rst`` seccion
>   "Defectos abiertos / cerrados" con severidad y cita commit del
>   fix.
> - **Training material** -> ``docs/source/`` segun audiencia
>   (operadores: ``operaciones/``; usuarios finales: pendiente
>   estructura).
> - **Product Acceptance Sign-off** -> ``progreso-<slug>.rst``
>   seccion "Sign-off PD" con fecha, firmante, condiciones.
> - **Lecciones aprendidas (RUP completo)** ->
>   ``docs/source/gestion/pm/<submodulo>/lecciones-aprendidas/``
>   archivo nuevo + cross-link desde ``progreso-<slug>.rst``.
> - **Milestone PD alcanzado** -> ``progreso-<slug>.rst`` seccion
>   "Milestone PD alcanzado <YYYY-MM-DDTHH:MM:SS>" con cita de
>   evidencia (URL produccion + log de cutover + Sign-off cite).
> - **Cierre formal** -> ``progreso-<slug>.rst::.meta::estado: COMPLETADA``.
>
> Ver `.claude/agents/rup-coordinator.md` para el mapping completo.

> *"Transition is not just deployment — it's the transfer of ownership from the project team to the users and operations team. The product release is a milestone, not the end."*

Ejecuta la fase **Transition** de RUP. Despliega el sistema a usuarios reales, conduce la aceptación del usuario, resuelve defectos identificados post-beta, y obtiene el milestone **PD (Product Release)** para el cierre formal del proyecto.

**THYROX Stage:** Stage 11 TRACK/EVALUATE / Stage 12 STANDARDIZE.

**Milestone:** PD — Product Release.

---

## Pre-condición

Requiere que la iniciativa activa en
``docs/source/gestion/pm/<submodulo>/iniciativas/<slug>/`` tenga
cierre de Construction documentado:

- ``progreso-<slug>.rst`` con seccion "Milestone IOC alcanzado".
- ``progreso-<slug>.rst`` con seccion "Deuda tecnica" cuantificada
  y acotada.
- Performance cumpliendo NFR en staging (citas P95 / latencia /
  throughput en progreso).
- Severity 1 = 0 en la seccion "Defectos abiertos" del progreso.

---

## Cuándo usar este paso

- Cuando el IOC de Construction está alcanzado
- Para cada ciclo de corrección post-beta (nueva iteración de Transition)
- Cuando los usuarios beta identificaron defectos críticos que requieren un nuevo beta antes del release final

## Cuándo NO usar este paso

- Sin IOC alcanzado — Transition con defectos críticos pendientes garantiza una experiencia de usuario negativa que daña la adopción
- Si el sistema ya está en producción y aceptado — PD fue alcanzado; iniciar el Stage siguiente THYROX

---

## Tabla de intensidad de disciplinas en Transition

| Disciplina | Intensidad en Transition | Foco principal |
|-----------|-------------------------|----------------|
| Business Modeling | Nula | Dominio ya modelado |
| Requirements | Baja | Solo cambios críticos encontrados en beta |
| Analysis & Design | Baja | Correcciones puntuales de defectos |
| Implementation | Media | Bug fixes, ajustes post-beta |
| Test | **Alta** | UAT, regression testing, performance en producción |
| Deployment | **Alta** | Release management, rollout plan |
| Config & Change Mgmt | **Alta** | Change freeze, hotfix process |
| Project Management | Media | Seguimiento de defectos, comunicación con stakeholders |
| Environment | Media | Preparación del entorno de producción |

---

## Actividades

### 1. Preparar el deployment

Antes de desplegar a producción o al entorno beta:

| Elemento | Contenido | Criterio de completitud |
|----------|-----------|------------------------|
| **Deployment Plan** | Pasos de instalación, configuración, rollback | Probado en staging por alguien distinto al que lo escribió |
| **Release Notes** | Nuevas features, defectos corregidos, breaking changes, instrucciones de migración | Revisado por el PO o sponsor |
| **Rollback Plan** | Cómo revertir si el deployment falla | Tiempo de rollback estimado y probado |
| **Communication Plan** | A quién notificar, cuándo, con qué mensaje | Stakeholders + usuarios + soporte informados con anticipación |
| **Support documentation** | FAQs, guías de usuario, runbooks de operaciones | Disponible antes del deployment |

### 2. Beta release y User Acceptance Testing (UAT)

El beta testing con usuarios reales es el corazón de Transition:

| Actividad | Descripción | Artefacto |
|-----------|-------------|-----------|
| **Selección de usuarios beta** | Representativos del usuario real — no solo el equipo de desarrollo | Lista de usuarios beta con roles |
| **Plan de UAT** | Scenarios de prueba basados en los UC críticos del Vision Document | UAT Plan con casos por UC |
| **Ejecución de UAT** | Usuarios ejecutan los scenarios y reportan defectos | UAT Results con defectos encontrados |
| **Clasificación de defectos** | Severity 1 (crítico), 2 (mayor), 3 (menor), 4 (cosmético) | Defect log con prioridad |
| **Feedback de usabilidad** | Observar a los usuarios usando el sistema — no solo preguntar | Notas de observación + grabaciones si aplica |

**Severidad de defectos:**

| Severity | Definición | Acción en Transition |
|----------|-----------|---------------------|
| **1 — Critical** | Sistema inusable; pérdida de datos; funcionalidad crítica rota | Corregir antes del PD — no negociable |
| **2 — Major** | Feature importante no funciona; workaround muy costoso | Corregir si es posible antes del PD; documentar si se difiere |
| **3 — Minor** | Feature funciona pero con limitaciones; workaround existe | Puede deferirse a release posterior |
| **4 — Cosmetic** | Estético o de UX menor | Diferir a release posterior |

**Priorización intra-severidad — cuando hay múltiples defectos del mismo nivel:**

| Criterio de priorización | Descripción | Peso |
|--------------------------|-------------|------|
| **Frecuencia de impacto** | ¿Cuántos usuarios o flujos afecta? (alto = más usuarios afectados) | Alto |
| **Bloqueo de UC crítico** | ¿Bloquea un UC Must Have del Vision Document? | Alto |
| **Costo de corrección** | ¿Qué tan complejo es corregir? (menor costo → antes) | Medio |
| **Disponibilidad de workaround** | ¿Hay forma alternativa de completar el flujo? (sin workaround → antes) | Medio |
| **Risk de regresión** | ¿La corrección puede introducir nuevos defectos? (alto risk → más tarde) | Bajo |

> **Regla:** Dentro de Severity 1 y Severity 2, priorizar por frecuencia de impacto × bloqueo de UC crítico. No corregir Severity 2 antes de que todos los Severity 1 estén cerrados.

### 3. Training y transferencia de conocimiento

| Audiencia | Contenido | Formato |
|-----------|-----------|---------|
| **Usuarios finales** | Cómo usar el sistema para sus tareas principales | Guía de usuario + sesión de training |
| **Equipo de operaciones** | Cómo mantener, monitorear y responder a incidentes | Runbook + sesión técnica |
| **Equipo de soporte** | Preguntas frecuentes, problemas conocidos, escalación | FAQ + troubleshooting guide |
| **Sponsor / negocio** | Qué entregó el proyecto vs lo prometido en el business case | Reporte de entrega |

### 4. Lecciones aprendidas del proyecto RUP completo

Al alcanzar el PD, documentar lecciones por fase y por disciplina:

| Dimensión | Preguntas |
|-----------|-----------|
| **Inception** | ¿La visión fue correcta? ¿El business case fue realista? ¿Los riesgos identificados fueron los correctos? |
| **Elaboration** | ¿El Architecture Prototype probó los riesgos correctos? ¿El SAD fue útil durante Construction? |
| **Construction** | ¿El plan de iteraciones fue realista? ¿La deuda técnica fue manejada bien? ¿La velocidad fue consistente? |
| **Transition** | ¿El sistema fue bien recibido por los usuarios? ¿El deployment fue sin problemas? ¿El UAT reveló surpresas? |
| **Proceso RUP** | ¿Cuáles disciplinas generaron más valor? ¿Qué se hubiera podido simplificar? |

### 5. Cierre formal del proyecto

| Acción | Descripción |
|--------|-------------|
| **Product Acceptance Sign-off** | Documento formal donde el sponsor/cliente acepta el sistema entregado |
| **Archivado de artefactos** | Vision Document, SAD, Use Case Model, Risk List final, UAT Results |
| **Release del equipo** | Miembros del equipo asignados a otros proyectos |
| **Post-implementation review** | 30-60 días después del deployment: ¿el sistema cumple el business case? |

---

## Criterio de milestone PD — ¿cerrar o nueva iteración?

**Alcanzar PD (todos los siguientes deben cumplirse):**
1. Sistema desplegado en producción (o entorno objetivo final)
2. Defectos Severity 1 = 0 en producción
3. Usuarios finales aceptaron formalmente (Product Acceptance Sign-off)
4. Training completado para usuarios y equipo de operaciones
5. Documentación completa y entregada

**Nueva iteración de Transition (cualquiera de los siguientes):**
- Ciclo de correcciones post-beta con defectos Severity 1 o 2 significativos
- Nueva beta requerida antes del release final (UAT reveló problemas mayores)
- Stakeholders rechazan el Product Acceptance Sign-off con justificación

---

## Artefacto esperado

Los entregables canonicos RUP de Transition se materializan en
artefactos de la iniciativa + acciones reales de deployment (ver
banner de adaptacion kaupamex v2 al inicio):

- ``tareas-<slug>.rst`` — T-NNN de deployment + handoff a
  iniciativa server submodulo si el despliegue toca infra.
- ``progreso-<slug>.rst`` — UAT iters + Defect log + Sign-off PD +
  "Milestone PD alcanzado" + cierre formal.
- ``docs/source/gestion/pm/<submodulo>/lecciones-aprendidas/`` —
  archivo nuevo con las lecciones del proyecto RUP completo.
- Commits de deployment en submodulos correspondientes (server +
  api + ui).

Template historico (estilo `.md`):
[transition-report-template.md](./assets/transition-report-template.md).
Conserva la estructura conceptual; al portar a `.rst` se reparte
entre los artefactos arriba.

---

## Red Flags — señales de Transition mal ejecutada

- **Transition como segundo proyecto de correcciones** — si Transition se extiende más de 20% del esfuerzo total del proyecto, los defectos son demasiados y Construction no fue completada correctamente
- **UAT sin usuarios reales** — *"el equipo de QA hizo el UAT"* no es UAT; los usuarios finales deben usar el sistema
- **PD sin Product Acceptance Sign-off formal** — *"el cliente dijo que estaba bien por email"* no es aceptación formal del sistema
- **Training pospuesto post-deployment** — usuarios que no saben usar el sistema en el primer día generan una primera impresión negativa difícil de revertir
- **Lecciones aprendidas omitidas por presión de cierre** — las lecciones aprendidas son el activo más valioso para el próximo proyecto RUP; no omitirlas
- **Defectos Severity 2 acumulados sin priorizar** — si hay muchos Severity 2 diferidos, la experiencia del usuario en producción será degradada; planificar una primera release de mantenimiento

---

## Carpetas externas relacionadas en docs/source/

Transition consume y produce contenido en estas carpetas (aparte
de los artefactos de la iniciativa y de los commits de deployment):

- ``docs/source/devops/`` — material operativo de despliegue:

  - ``despliegue-produccion.rst`` — runbook de cutover; la
    iniciativa hace cross-link y agrega seccion al cierre si el
    deployment introduce un paso nuevo.
  - ``setup.rst`` + ``setup-windows-gitbash.rst`` — guias de
    entorno actualizadas si la Transition cambia el setup.

- ``docs/source/onboarding/guia-primer-dia.rst`` — referencia para
  training de usuarios o nuevos colaboradores; actualizar si el
  release cambia el flujo de onboarding.

- ``docs/source/gestion/pm/<submodulo>/lecciones-aprendidas/`` —
  archivo nuevo por iniciativa cerrada con lecciones del ciclo RUP
  completo. Cross-link desde ``progreso-<slug>.rst`` al cierre.

- ``docs/source/implementacion/auditoria-sprint-*.rst`` — precedent
  del formato de retrospectiva multi-sprint; util si la Transition
  cierra varias iteraciones Construction.

- ``docs/source/databases/estrategia-bases-de-datos.rst`` — si la
  Transition requiere ajustes de estrategia DB en produccion,
  actualizar este archivo.

- ``docs/source/normativa/procedimientos/`` — si el cutover define
  un procedimiento nuevo (rollback, monitoring, alerting), agregar
  ``proc-<nombre>.rst`` aqui.

- ``docs/source/risks-technical-debt/registro-riesgos-y-deuda-tecnica.rst``
  — cualquier deuda residual sobreviviente a Transition se promueve
  a P-NN o C-NN aqui antes del cierre formal.

- Submodulo ``server/`` — la operacion real de deployment ocurre en
  iniciativas hermanas bajo ``docs/source/gestion/pm/server/iniciativas/``.

## Estado activo

En kaupamex **no hay `now.md`**. El estado y la coordinacion
intra-sesion **persisten en ``docs/source/``**, en los `.rst` de la
iniciativa. La fase activa se lee del campo ``:estado:`` del
metadata de ``progreso-<slug>.rst`` y de la ultima seccion de su
bitacora.

**Al INICIAR Transition:** abrir entrada de bitacora
"Transition iter 1" (o numero subsiguiente) en
``progreso-<slug>.rst``. Mantener ``:estado:`` en ``En ejecucion``.

**Al COMPLETAR** (PD alcanzado): agregar seccion
"Milestone PD alcanzado <YYYY-MM-DDTHH:MM:SS>" en
``progreso-<slug>.rst`` con cita de evidencia: URL de produccion,
log de cutover, Sign-off PD con fecha y firmante. Marcar
``progreso-<slug>.rst::.meta::estado: COMPLETADA`` y registrar la
ultima entrada de bitacora de cierre.

## Siguiente paso

- PD alcanzado → RUP completado; iniciar Stage siguiente THYROX (TRACK/EVALUATE o STANDARDIZE)
- PD no alcanzado → nueva iteración de `rup:transition` con lecciones documentadas

---

## Limitaciones

- La aceptación de usuarios no garantiza el éxito a largo plazo — monitorear métricas de adopción y satisfacción 30-90 días después del deployment
- Defectos encontrados post-deployment en producción (no en staging) revelan limitaciones del entorno de prueba — mejorar la paridad staging/producción para el próximo proyecto
- El período post-PD de soporte inmediato (hypercare) no está cubierto en este skill — planificarlo como actividad de operaciones separada

---

## Reference Files

### Assets
- [transition-report-template.md](./assets/transition-report-template.md) — Template completo: plan de deployment, UAT results, defect log, training, lecciones aprendidas RUP completo, Product Acceptance Sign-off, checklist PD

### References
- [pd-criteria.md](./references/pd-criteria.md) — Criterios de evaluación PD: sistema en producción, Severity 1=0, Product Acceptance Sign-off, training completo, user acceptance criteria, límites de tiempo para Transition
