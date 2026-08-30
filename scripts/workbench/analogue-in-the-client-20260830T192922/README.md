# ¿Tiene el cliente un análogo de `.claude/eventos/`?

Medido sobre el volcado versionado de `/opt/claude-code/bin/claude` **2.1.251**
(214 326 616 bytes), que este mismo trabajo vendorizó en
`docs: tools/claude-code-bin/2.1.251/`. La
versión la decide el contenido del volcado, no el reloj: el literal `N.N.N`
más frecuente gana con **2048** contra 129 del segundo — margen de 15.9×.

## La respuesta corta

**No, y la forma en que no lo tiene es informativa: el cliente tiene las dos
mitades por separado, y ninguna de las dos es esto.**

| Mecanismo del cliente | Qué comparte | Qué le falta |
|---|---|---|
| **`Workflow`** | identificador propio por corrida (`wf_…`), guion persistido (`scriptPath` 91), registro de la ejecución (`journal` 96), fases (`phases` 39), reanudable (`resumeFromRunId` 15) | **la durabilidad**. El propio ejecutable lo dice: *«persists its script to a file under the session directory»*. Muere con la sesión, no se versiona, y no lleva premisa, métrica ni ceguera. |
| **Skill** | **la anatomía exacta**: `SKILL.md` 98 + `scripts/` 31 + `references/` 26 + `assets/` 4 — documento rector, instrumento y material de apoyo, versionado en el repo | **la fecha**. Un skill es reusable y se invoca N veces; no guarda la evidencia de ninguna ejecución concreta. |

Lo que `.claude/eventos/` hace es **la intersección que el cliente no tiene**:
una corrida fechada **cuya evidencia se versiona**. Por eso es un mecanismo del
proyecto y no una copia — y por eso no hay término del cliente que tomar
prestado.

Los otros directorios que el cliente sí persiste bajo `.claude/` —
`checkpoints/`, `worktrees/`, `mailbox/`, `routines/.state/` — son **estado del
cliente**, no trabajo del proyecto. No compiten por el nombre.

## Qué significa para el nombre

Las dos palabras que el cliente usa para cada mitad están **tomadas**:

- **`run`** — es su palabra para la corrida (`run_id`, `resumeFromRunId`,
  `wf_`), y aquí choca de frente con `RUN_ID`, con las corridas de pytest y
  con las de CI.
- **`skill`** — es su palabra para la anatomía, y ya nombra otra cosa en este
  árbol: `.claude/skills/`.

Así que el nombre tiene que ser nuestro. `workbench` sobrevive con **una
colisión blanda declarada**: sus 4 ocurrencias en el ejecutable son una sola
cadena, `workbench.action.terminal.sendSequence`, que es un **comando de VS
Code** — vocabulario del editor, no del cliente. No hay ningún `workbench` en
el vocabulario propio de Claude Code.

## La corrección de mi propia medición

Antes de este trabajo afirmé *«`workbench` da 0 hits en el ejecutable»*. **Da
4.** La primera medición usó un patrón entrecomillado
(`"workbench"|'workbench'|workbench:`) contra el binario crudo; ésta usa
`\bworkbench\b` sobre el volcado de cadenas. El instrumento decidía la
conclusión — sub-patrón **A** de `metrica-decide-la-conclusion.md`, cometido
al medir contra ese mismo defecto.

El veredicto no cambia, pero la cifra publicada sí, y una cifra que no se
corrige envejece hacia la mentira.

*Métrica:* líneas del volcado que contienen cada literal (`grep -ac`), y las
ocurrencias con 70 caracteres de contexto para desambiguar el sentido.
*Ciega a:* un mecanismo que el cliente construya sin literal; la documentación
web de Anthropic, que no se midió; y si un literal declarado está cableado a
algo — un nombre presente no prueba un mecanismo vivo.

## Segunda población: los cuatro repos de referencia de AI

La pregunta no se agota en el cliente. `/home/user` tiene cuatro repos de
referencia de AI —`skills`, `agency-agents`, `claw-code`, `coreutils`— y
ninguno tiene el mecanismo:

| Repo | Directorios de trabajo fechado o instrumentado |
|---|---|
| `skills` | **0** |
| `agency-agents` | **0** |
| `claw-code` | **0** |
| `coreutils` | **0** |

`skills` es el más cercano en espíritu —`.agents/` con sus ADR, `skills/` con
la anatomía `SKILL.md` + `scripts/`— y **no guarda la evidencia de ninguna
ejecución**: no hay `outputs/`, `evidence/` ni `runs/` en todo el árbol. Es la
misma mitad que el cliente: artefacto durable sin fecha.

Los términos que sí usan, y para qué:

| Término | Archivos que lo nombran | Qué nombra ahí |
|---|---|---|
| `workflow` | 287 | el flujo de CI y el de una skill |
| `evidence` | 144 | la evidencia *dentro* de un documento, no un directorio |
| `artifact` | 54 | la salida publicada |
| `playbook` · `runbook` | 34 · 18 | procedimiento repetible, sin fecha |
| `journal` | 7 | registro de eventos |
| **`workbench`** · **`worksite`** | **0** · **0** | — |

*Métrica:* directorios de profundidad ≤3 cuyo nombre marque una unidad fechada
o instrumentada; y archivos `.md`/`.json`/`.rs` que nombran cada término.
*Ciega a:* un mecanismo que un repo tenga sin nombrarlo en esos formatos — se
midió por nombre de directorio y por literal, no leyendo cada repo entero.

## Veredicto

**El mecanismo es nuestro.** Ni el cliente ni los cuatro repos de referencia
lo tienen: los cinco tienen artefactos durables sin fecha, o corridas fechadas
sin durabilidad. Nadie versiona la evidencia de una ejecución concreta.

Por tanto no hay término que tomar prestado, y el nombre tiene que ser propio.
**`workbench` se sostiene**: 0 ocurrencias en los cuatro repos de referencia, y
en el ejecutable sus únicas 4 son una cadena de VS Code. La colisión blanda
queda declarada aquí para que nadie la redescubra.
