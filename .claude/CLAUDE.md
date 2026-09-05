```yml
type: Contexto Persistente
version: 4.0.0
updated_at: 2026-07-17 19:33:06
```

# CLAUDE.md — kaupamex

**Level 2 — Puente entre [SKILL](skills/thyrox/SKILL.md) (Level 1) y proyecto.**

**Identidad — tres capas distintas (no confundir):**

- **Repositorios en GitHub:** los cinco submodulos
  `jcg-admin/kaupamex-{api,db,docs,server,ui}` (renombrados desde `e-comerce-*`
  el 2026-07-23, DEC-KX-06). El superproyecto `jcg-admin/kaupamex` existe pero
  **esta ausente por decision** del ejecutor desde 2026-08-07: el arbol tiene
  los cinco clones hermanos, no el padre (ver `gitlink-bump-gate.md`).

- **Producto / plataforma: Kaupamex.** Es el **operador L0**: un SaaS
  multi-empresa que hospeda a empresas cliente para gestionar su ecommerce +
  ERP + CRM, con cobro por modulo + renta mensual. El nombre del repo coincide
  con el operador L0 a proposito. Dentro del codigo: bases `kaupamex_db` /
  `kaupamex_qa`, rol `django_user`, `SYSTEM_COMPANY_CODE = 'kaupamex_global'`,
  env files en `src/.env`, punto de entrada `kaupamex-bin`.

- **Una empresa L1 no es el producto.** Un L1 es una `Company` cliente que
  la plataforma hospeda, no el operador ni "el producto" como un todo.
  **En prosa no se usa "founder"** — implica que fundo u opera la plataforma,
  que es exactamente lo contrario (ver `terminologia-l0-company.md`).
  **El L1 tampoco se nombra en prosa** desde el barrido del 2026-09-05: se
  dice "la empresa L1", sin nombre propio.

**El L1 ya no se nombra en codigo (DEC-3 de `tenants-sin-clases-en-codigo`,
2026-08-05).** La constante `FOUNDER_COMPANY_CODE`, cuyo valor nombraba al L1, **fue
retirada**: la empresa inicial se declara en config (`BOOTSTRAP_COMPANY_CODE`
/ `BOOTSTRAP_COMPANY_NAME`, ambas con `default=''`) y la crea
`kaupamex-bin company_create`. Con esas claves vacias no se siembra ninguna
empresa — `seed()` es un no-op.

Es **mas abstracto que la referencia**, que si siembra un placeholder:
`odoo19c: base/data/res_company_data.xml:5` declara `name = "My Company"`, y
lo hace igual en los doce arboles medidos (19, 18 y 16; Community y
Enterprise). La referencia nunca nombra una empresa real; su data de **demo**
usa una ficticia (`ProBike Inc`, `res_company_demo.xml`).

Regla de clasificacion de config: infra/ops → L0 (Kaupamex); per-empresa
(contacto, newsletter, remitente transaccional) → L1/L3 (`CompanySetting`).
Ver DEC-KX-05 (iniciativa `plataforma-kaupamex`).

**El barrido del 2026-09-05 retiro el nombre del L1 de los cinco repos** —
3972 sustituciones, por directiva del ejecutor. Lo unico que lo conserva, a
proposito, es la **evidencia fechada** (hallazgos, analisis, progreso, audits,
lecciones) y las **cinco iniciativas cuyo slug lo lleva** —
`crear-practicayoruba-db`, `integrar-practicayoruba-db-api`,
`crear-practicayoruba-server`, `configurar-red-dmz-practicayoruba-server` y
`analizar-impacto-renombrar-practicayoruba-a-src`— con **37 archivos** que lo
llevan en el nombre. Fuera de esos dos casos, el nombre del L1 no aparece.

**Esas cinco NO se renombran: se marcan `deprecated`** (directiva del ejecutor
2026-09-05; el identificador va en ingles, igual que el `DEPRECATED:` de los
guiones). Cada `index.rst` abre con `.. deprecated:: 2026-09-05`, que declara
que **lo deprecated es el slug, no el trabajo**: las cinco quedaron
`completada` y siguen vigentes. No se abre trabajo nuevo bajo ellas; una
sucesora se nombra segun `terminologia-l0-company`.

Renombrarlas romperia **17 `:doc:` alojados en `audits/`**, que es evidencia
congelada — medido, no supuesto: los toctree de iniciativas usan `:glob:` (0
entradas por nombre) y **ninguna** de sus 35 etiquetas se cita con `:ref:`
desde fuera. La version anterior de este parrafo decia "4 slugs", "24
archivos" y "renombrarlos rompe rutas y `:ref:` vivos": las dos cifras y la
razon eran falsas. Ver H-DOCS-1051.

**Nota de adaptacion (2026-05-19):** este archivo proviene del template
THYROX usado en IACT-docs. Para kaupamex se decidio **no importar**
el directorio `.thyrox/` — la funcionalidad que THYROX coloca en
`.thyrox/context/` (estado de proyecto, work packages, decisiones,
focus, technical-debt) vive aqui en el submodulo `docs/` bajo
`source/gestion/pm/`. El SKILL `thyrox` se conserva como referencia
metodologica.

## Locked Decisions (no revisitar)

Estas son reglas del framework de metodologia — NO son ADRs del proyecto.
Los ADRs del proyecto viven en el path declarado por `adr_path` en este archivo (ver sección Configuración del Proyecto).

1. **ANALYZE first** — No planificar sin entender primero
2. **Anatomía oficial** — SKILL.md + scripts/ + references/ + assets/
3. **Git as persistence** — Zero archivos backup, historial en git
4. **Markdown only** — Sin bases de datos, sin formatos propietarios
5. **Single skill** — Un `thyrox` con references, no 15 skills separados
   *Addendum FASE 22:* Los `workflow-*` skills son la excepción intencional: son herramientas de ejecución por fase, no skills de dominio tecnológico. Esta excepción está documentada en ADR-016. La regla original sigue vigente para tech skills (python, react, etc.).
   *Addendum FASE 23:* Nomenclatura resuelta a kebab-case hyphens — `workflow-*/SKILL.md`. TD-019 cerrado (FASE 23).
   *Addendum FASE 29:* Skill renombrado → `thyrox` (prefijo `pm-` eliminado — no es PM de PMI, es la metodología THYROX misma). TD-020 cerrado (FASE 29).
   *Addendum FASE 31:* Interfaz pública del sistema → `/thyrox:*` (plugin namespace via `.claude-plugin/plugin.json`). Los `workflow-*` skills permanecen como implementación interna. Capa de presentación complementa ADR-016. Ver ADR-019. TD-036 cerrado (FASE 31).
   *Addendum FASE 35:* Estado de sesión y work packages migrados a `.thyrox/context/` — fuera de `.claude/` (zona de configuración de Claude Code).
   *Addendum FASE 39:* 12 fases THYROX propias (DISCOVER → STANDARDIZE). `workflow-analyze` renombrado a `workflow-discover`. 12 skills workflow-* totales: workflow-discover, workflow-measure, workflow-analyze, workflow-constraints, workflow-strategy, workflow-plan, workflow-structure, workflow-decompose, workflow-pilot, workflow-execute, workflow-track, workflow-standardize. Sistema `.claude/rules/` creado para invariantes globales.
   *Addendum kaupamex 2026-05-19:* `.thyrox/` no se importa. El rol de `.thyrox/context/` (estado, decisiones, deuda tecnica, work packages) se cumple en el submodulo `docs/` bajo `source/gestion/pm/`. Decisiones de documentacion siguen en `docs/source/gestion/decisiones/`; ADRs de producto van a `docs/source/backend/adr/` o `docs/source/frontend/adr/` segun corresponda.
6. **Work packages with timestamp** — `docs/source/gestion/pm/<submodulo>/iniciativas/<slug>/` (slug kebab-case estable). En kaupamex no se usa el prefijo timestamp: el slug es estable, el git log registra la fecha. Heredado de THYROX pero adaptado al naming de IACT-docs/source/gestion/pm/.
7. **Tim Pope commit style** — Subject imperativo recomendado **≤50 ch** (máximo absoluto: 72), capitalizado y sin punto + línea en blanco + body con QUÉ y POR QUÉ, wrapped a 72 ch. Reemplaza Conventional Commits desde ÉPICA 4 (repository-diagnostics). Ver `.claude/rules/commit-conventions.md`.
8. **Changelog en dos niveles** — `track/{wp}-changelog.md` se actualiza siempre durante el WP. `CHANGELOG.md` raíz **solo** se modifica en merge a `main` con bump de versión. Ver `.claude/rules/changelog-policy.md`.

## SKILL vs ADR — Regla de uso

|                  | SKILL.md                                     | ADR en {adr_path}                              |
|------------------|----------------------------------------------|--------------------------------------------------------|
| Que es           | Instrucciones de metodologia (como trabajar) | Registro de decision tomada (por que se eligio X)      |
| Quien lo escribe | Mantenedor del sistema                       | Claude en Phase 1-2, cuando hay decision permanente    |
| Cuando modificar | Solo si cambia la metodologia de gestion     | Al tomar una decision arquitectonica del proyecto      |
| Duracion         | Vive con el sistema                          | Inmutable una vez aprobado                             |

REGLA: Si la duda es "documento esto en SKILL.md o en un ADR?":
- Cambia COMO se trabaja en general -> SKILL.md
- Registra POR QUE se eligio algo en este proyecto -> ADR en {adr_path}

## Estructura

```
.claude/                       ← Configuración y extensiones de Claude Code
├── CLAUDE.md                  ← Este archivo (Level 2)
├── agents/                    ← Agentes nativos Claude Code (ver references/agent-spec.md)
├── commands/                  ← Comandos slash disponibles
├── memory/                    ← Memoria persistente entre sesiones
├── references/                ← Documentación global de plataforma Claude Code (on-demand)
├── rules/                     ← Reglas globales cargadas en cada sesión
├── scripts/                   ← Scripts de infraestructura Claude Code
└── skills/                    ← Skills del sistema (thyrox + workflow-* + tech-stack)
    └── thyrox/                ← El SKILL (Level 1): SKILL.md + references/ + scripts/ + assets/

docs/source/gestion/           ← Sustituto de .thyrox/context/ en este proyecto
├── index.rst
├── plantilla-adr.rst          ← Template ADR de producto
├── decisiones/                ← DEC-DOC (documentation decisions)
└── pm/                        ← Project Management — estado del proyecto vive aqui
    ├── index.rst
    ├── siguiente-mejor-decision.rst  ← LEER AL INICIO DE CADA SESION
    ├── <submodulo>/           ← api|db|docs|server|ui
    │   ├── index.rst
    │   ├── iniciativas/<slug>/ ← Equivalente a .thyrox/context/work/
    │   │   ├── index.rst
    │   │   ├── alcance-<slug>.rst
    │   │   ├── analisis-<slug>.rst
    │   │   ├── decisiones-<slug>.rst
    │   │   ├── progreso-<slug>.rst
    │   │   └── tareas-<slug>.rst
    │   ├── audits/             ← Auditorias transversales + hallazgos extraidos
    │   ├── lecciones-aprendidas/ ← Deep-reviews y retrospectivas
    │   ├── checklists/         ← Listas de verificacion reutilizables
    │   └── matrices/           ← Trazabilidad cruzada (req vs UC, UC vs modulo, etc.)
    └── plan-documentacion-pendiente.rst
```

**Por que no `.thyrox/`:** importar el directorio en kaupamex no aportaba
valor — su tooling (registry/_generator.sh, bootstrap.py) esta orientado
a generar skills y guidelines en proyectos sin documentacion estructurada.
kaupamex ya tiene Sphinx + RST y la convencion `source/gestion/pm/` que
hereda de IACT-docs, asi que el estado del proyecto vive en docs/ donde
es buscable, indexable y publicable.

## Tech-stack — Stack confirmado

Stack del multi-repo (5 repositorios hermanos):

- **api/**: Django 6.0.5 + DRF 3.16.1, psycopg[binary] >=3.2, simplejwt 5.5.1,
  drf-spectacular 0.29.0, pytest + pytest-django + factory-boy, mercadopago SDK.
- **ui/**: React 19, Redux Toolkit 2.0, @tanstack/react-query 5.x,
  react-router-dom 6.x, Webpack 5.88, Babel 7.29, Jest 29 + RTL 16, SCSS
  con sass-loader, framer-motion, recharts, dompurify.
- **db/**: PostgreSQL 16 (ADR-028; mínimo efectivo 14), provisionada con
  bash + python-dotenv.
- **server/**: Ubuntu 24.04 + Apache 2.4 + mod_wsgi + Let's Encrypt
  (acme.sh) + fail2ban + SSH hardening.
- **docs/**: Sphinx 8.2 + Furo + plantuml + sphinx-design + sphinx-tabs,
  build con uv y Makefile (`make html`).

**Guidelines tech-stack (@imports):** deshabilitados por ahora. En IACT-docs
los `.thyrox/guidelines/*.instructions.md` se importan con `@`-imports
automaticos. En kaupamex el directorio `.thyrox/` no existe; los skills
tech-stack que ya viven en `.claude/skills/{frontend-react, frontend-webpack,
db-mysql, sphinx}` cubren la mayoria de los casos al invocarse via Skill
tool. Si se necesita comportamiento siempre-activo (no on-demand), los
candidatos se documentaran en `docs/source/gestion/pm/checklists/` como
listas de verificacion estables, no como auto-imports.

## Reglas de edición — OBLIGATORIO

Aplicar en TODA edición de archivo, sin excepción:

1. **`updated_at` es automático** — Si el archivo que se está editando tiene `updated_at` en su frontmatter, actualizarlo al timestamp actual (`date '+%Y-%m-%d %H:%M:%S'`) en el mismo Edit. No es un paso separado, no requiere que el usuario lo pida, no requiere GATE OPERACIÓN. Es una edición consecuencia — ocurre siempre.

2. **Un solo Edit por archivo** — Nunca hacer dos Edits separados al mismo archivo: uno para el contenido y otro para `updated_at`. Ambos cambios van en la misma llamada.

3. **`updated_at` no aplica a artefactos de iniciativa** — Los archivos dentro de `docs/source/gestion/pm/<submodulo>/iniciativas/<slug>/` (alcance, analisis, hallazgos, tareas, progreso) usan metadata RST (`.. meta::`, p. ej. `:fecha_creacion:`) y no se actualizan como documentos vivos. No agregar `updated_at` donde no existia.

## Flujo de sesión — OBLIGATORIO

SIEMPRE seguir este flujo. NO omitir pasos.

1. **Inicio** —
   a. Leer **`docs/source/gestion/pm/siguiente-mejor-decision.rst`** (fuente canónica de "¿qué es lo siguiente?"). Anti-staleness check obligatorio: si `:fecha_actualizacion:` > 7 días o `:commit_referencia:` no coincide con HEAD del repo docs → refrescar antes de confiar. Consultar secciones "Snapshot estado actual" y "Siguiente paso recomendado".
   b. Revisar el indice de iniciativas del submodulo activo en `docs/source/gestion/pm/<submodulo>/iniciativas/index.rst` y leer el `progreso-*.rst` mas reciente de la iniciativa en curso.
2. **Activar SKILL** — ANTES de responder cualquier tarea: invocar Skill tool → thyrox.
   Si el Skill tool no está disponible: leer [SKILL.md](skills/thyrox/SKILL.md) completo y seguirlo paso a paso.
3. **Identificar fase activa** — Revisar `docs/source/gestion/pm/<submodulo>/iniciativas/<slug>/`:
   - Hay una iniciativa activa → continuar en la fase donde quedó (ver `progreso-<slug>.rst`).
   - No hay iniciativa activa → empezar Phase 1: DISCOVER, crear nuevo `<slug>/` con `alcance-<slug>.rst` inicial.
4. **Trabajar** — Seguir cada fase hasta su exit criteria. NO saltarse fases. Commits estilo Tim Pope (ver `.claude/rules/commit-conventions.md`).
5. **Cierre** — Actualizar `progreso-<slug>.rst` con el estado final del WP. Si la iniciativa cierra, marcar `:estado: COMPLETADA` en el `index.rst` de la iniciativa y refrescar `docs/source/gestion/pm/siguiente-mejor-decision.rst` (triggers documentados en la sección "Actualización del documento" de ese archivo).

### Protocolo de Completación de Fase (I-015: Invariante Crítica)

**REGLA INVIOLABLE:** Antes de reportar cualquier phase/WP como "complete", "done", o "finished":

```bash
bash .claude/scripts/validate-phase-completion.sh
```

El script valida 5 condiciones:
1. Working tree clean (sin cambios unstaged)
2. No staged changes (nada pendiente de commit)
3. Remote sync (todos los commits pusheados)
4. Build success (make html exit 0)
5. Recent commits (hay historial)

**Resultado:**
- Exit code 0 = SEGURO reportar completación
- Exit code 1 = NO reportar hasta fijar los problemas

**Nunca** reportar completación sin este check. Ver ADR-phase-completion-validation-protocol.md para detalles y motivación.

## Multi-skill orchestration

Reglas cuando hay más de un skill activo en la misma sesión.

- **Máximo simultáneos:** 2-3 skills. Por encima de ese límite, el budget de context window para descripciones se satura y el triggering de todos se degrada.
- **Cuándo secuenciar:** Si skill B necesita output de skill A (e.g. tech-detector → python-mcp), ejecutar A hasta completar y commitear antes de activar B.
- **Section owners disjuntos:** Cada skill escribe en archivos distintos. Si dos skills necesitan tocar el mismo archivo, uno lo hace y el otro espera (o usa una sección marcada con `<!-- SECTION OWNER: {skill} -->`).
- **Naming de state files por skill:** En kaupamex los state files de sesion no se persisten en el filesystem (no hay `.thyrox/context/`). El estado de iniciativa vive en el `progreso-<slug>.rst` de cada iniciativa. Para coordinacion intra-sesion entre agentes paralelos, usar memoria del orquestador y tool outputs — no archivos `now-*.md`.
- **Campos requeridos al reportar agentes paralelos en `progreso-<slug>.rst`:** `agent_id`, `status` (running/completed/failed), `output_key`, `started_at`, `timeout_at`. Ver detalle: `.claude/references/parallel-agent-state-files.md`

## Convenciones de escritura — OBLIGATORIO

Estas convenciones aplican a TODO el código y texto generado por Claude en esta sesión
y en sesiones de agentes hijos. CLAUDE.md es el único artefacto cargado automáticamente
en todas las sesiones y heredado por agentes — por eso las convenciones universales viven aquí,
no en references/ (on-demand) ni en guidelines/ (on-demand).

### Preparación de inputs para análisis (input.md de textos externos)

**Regla:** Cuando se prepara un documento `input.md` que estructura un capítulo, paper o texto externo para análisis por agentes (`deep-dive`, `agentic-reasoning`, etc.), NO comprimir.

**Qué preservar verbatim:**
- Todo párrafo que contenga un claim técnico, arquitectónico, cuantitativo o de calidad
- Conclusiones completas (no solo la última frase)
- Párrafos de cierre de secciones (suelen contener las afirmaciones más fuertes)
- Código completo (no pseudocódigo ni resumen del código)
- Frases que niegan un defecto ("no meramente X") — son claims de calidad implícitos

**Qué puede estructurarse/comprimirse:**
- Introducción narrativa sin claims verificables
- Repeticiones de afirmaciones ya capturadas
- Ejemplos ilustrativos cuando el claim principal ya está captado

**Por qué esta regla existe:**
Las elecciones editoriales de qué comprimir son elecciones de qué NO analizar. Los agentes solo pueden evaluar lo que reciben. Si el input.md está incompleto, el análisis lo estará también — y el error será del orquestador, no del agente.

**Anti-patrón específico documentado:** En la sesión ÉPICA 42 (2026-04-18), al preparar el input de Cap.6 Planning v2.0.0, se comprimió la sección DeepResearch perdiendo: (1) integración de documentos privados, (2) "no mera concatenación" como garantía implícita de calidad, (3) párrafo de cierre de casos de uso. Cada uno generó claims adicionales no analizados inicialmente.

---

### Parámetro `description` del Agent tool

**Convención:** minúscula consistente (sentence case — primera palabra y nombres propios).

```python
# Correcto
Agent(description="deep-review de permisos en claude-howto", ...)
Agent(description="análisis de cobertura Phase 3 → Phase 4", ...)

# Incorrecto
Agent(description="Deep-review de permisos...", ...)
Agent(description="ANÁLISIS DE COBERTURA...", ...)
```

**Respaldo documental:**
- claude-howto `STYLE_GUIDE.md:144` — P3.1: sentence case para todos los encabezados y labels
- claude-code-ultimate-guide — ningún repo documenta explícitamente este parámetro,
  pero el ecosistema usa minúsculas para todos los valores de configuración
  (model names: `sonnet`, effort values: `low/medium/high`, kebab-case names)
- Fuente: `conventions-review-claude-howto.md` y `conventions-review-ultimate-guide.md`
  en WP `2026-04-14-09-13-51-context-migration/`

## Configuración del Proyecto

adr_path_doc:    docs/source/gestion/decisiones/     # DEC-DOC: decisiones de documentacion
adr_path_api:    docs/source/backend/adr/           # ADRs de producto, capa backend
adr_path_ui:     docs/source/frontend/adr/          # ADRs de producto, capa frontend
adr_path_thyrox: docs/source/thyrox/adr/            # ADRs de la IMPLEMENTACION de THYROX (ADR-THYROX-001)
pm_root:         docs/source/gestion/pm/            # Project management raiz; subdivide por raiz de trabajo
submodulos:      [api, db, docs, server, ui, thyrox] # Cada una tiene su gestion bajo pm_root/<raiz>/

# La clave `submodulos:` nombra mal lo que enumera, y se declara la deuda en vez
# de pagarla aqui. Ninguna de las seis es un submodulo: no hay superproyecto
# desde 2026-08-07 (`gitlink-bump-gate.md`), asi que no hay gitlink que las haga
# submodulos de nada — son clones hermanos. Y `thyrox` ademas no es una capa del
# producto: es su PROVEEDOR de metodologia, y los cinco kaupamex-* son sus
# consumidores. Lo que la clave enumera de verdad son las RAICES DE TRABAJO que
# el arbol de docs documenta. Ver ADR-THYROX-001; el renombre es la tarea #169.

## Glosario

| Término | Significado | Ejemplo |
|---------|-------------|---------|
| **ÉPICA N** | Iniciativa de trabajo del proyecto — número secuencial global. Cada WP ocupa una ÉPICA. Antes llamado "FASE N" (retrocompat). | ÉPICA 39: plugin-distribution · ÉPICA 40: multi-methodology |
| **Stage N** | Etapa del ciclo THYROX dentro de un WP (1-DISCOVER … 12-STANDARDIZE). Se reinicia en cada ÉPICA. Antes llamado "Phase N". | ÉPICA 40 está en Stage 5: STRATEGY |
| **WP** | Work package — directorio `docs/source/gestion/pm/<submodulo>/iniciativas/<slug>/` que contiene todos los artefactos de una ÉPICA | `docs/source/gestion/pm/docs/iniciativas/corregir-warnings-build-sphinx/` |
| **flow** | Metodología declarada por iniciativa en la clave `:flow:` del `alcance` (rup, scrum, kanban, tdd, pm, pdca, dmaic, lean, babok, bpa, cp, pps, sp, rm, ninguno; ver `metadata-standards.md`, DEC-R-01) | `:flow: rup` en el `.. meta::` del `alcance` |
| **methodology_step** | Paso actual de la metodología activa, con prefijo namespace | `pdca:do`, `dmaic:analyze`, `pm:executing` |
| **SP-NNN** | Stopping Point — punto de parada explícito definido en el Stopping Point Manifest de Stage 1 | SP-06: gate 6→7, esperar aprobación humana |

**Regla mnemotécnica:** ÉPICA es el "qué proyecto", Stage es el "en qué etapa del proyecto".
Un proyecto con 40 ÉPICAs tiene 40 WPs; cada WP recorre hasta 12 Stages internamente.

**Stages con renaming (desambiguación con metodologías):**
Stage 2 BASELINE (antes MEASURE) · Stage 3 DIAGNOSE (antes ANALYZE) ·
Stage 6 SCOPE (antes PLAN) · Stage 10 IMPLEMENT (antes EXECUTE)

**Retrocompatibilidad:** Los documentos históricos que usan "FASE N" y "Phase N" son válidos — se leen como sinónimos de ÉPICA y Stage respectivamente.

## Restricciones de fórmulas probabilísticas

Las siguientes fórmulas están prohibidas en artefactos THYROX:

1. **Forma simple:** `P₀ × e^(-r×d)` — decay exponencial sin calibración empírica propia
2. **Forma multiparámetro Part B:** `P(correct) = P₀ × e^(-Σλᵢxᵢ)` con 5+ parámetros — ratio de calibración 8%, calibración circular (misma observación para ajuste y validación)

**Por qué:** Estas fórmulas proyectan precisión cuantitativa sin derivación empírica verificable. Constituyen realismo performativo (ÉPICA 42).

**Alternativa válida:** afirmaciones calibradas con evidencia observable (`PROVEN/INFERRED/SPECULATIVE`) o estimaciones explícitamente marcadas como hipótesis.

## Para más contexto

- Metodología completa: [SKILL](skills/thyrox/SKILL.md)
- **Priorización y estado del proyecto:** [siguiente-mejor-decision.rst](../docs/source/gestion/pm/siguiente-mejor-decision.rst) — leer al inicio de CADA sesión (ver Flujo de sesión paso 1a)
- Project management raiz: [pm/index.rst](../docs/source/gestion/pm/index.rst)
- Iniciativas por submodulo: `docs/source/gestion/pm/{api,db,docs,server,ui}/iniciativas/`
- Decisiones de documentacion: [decisiones/index.rst](../docs/source/gestion/decisiones/index.rst)
- Plantilla ADR de producto: [plantilla-adr.rst](../docs/source/gestion/plantilla-adr.rst)
- Convenciones: [conventions](references/conventions.md)
