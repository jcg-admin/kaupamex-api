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

---

# Cómo lo maneja el cliente — el mecanismo, no sólo su existencia

La primera mitad de este trabajo respondió *si* el cliente tiene el mecanismo.
Ésta responde **cómo**, que es lo que se puede aprovechar.

## 1. La identidad no es una ruta: es una tupla `(namespace, scope)` validada

El cliente **no tiene «un directorio por trabajo»**. Tiene un espacio de
nombres con alcance validado. Los **19 namespaces** que declara:

```
transcript 42 · task 13 · job 13 · sidecar 10 · memory 10 · daemon 8 · log 5
session 4 · scratch 4 · state 3 · settings 3 · recording 3 · plan 3 · paste 3
mailbox 3 · cache 2 · team 1 · identity 1 · history 1 · azure 1
```

Cada uno declara **qué claves de alcance exige** para poder direccionar algo, y
el validador lo dice en prosa, verbatim:

| Namespace | Exige | Verbatim del ejecutable |
|---|---|---|
| sesión | `projectKey` | *«a session narrows one project folder, and no cross-project session filter exists»* |
| `scratch` | `sessionId` | *«a scratch relPath narrows one session directory, and no cross-session prefix filter exists»* |
| `job` | `jobId` | *«a job relPath narrows one job directory, and no cross-job prefix filter exists»* |
| subagente | `projectKey` + `sessionId` | *«an agentRelPath narrows the subagents/ tree of one session»* |
| memoria de agente | `agentType` | *«an agent-memory relPath narrows one agent directory»* |

**Lo que esto enseña.** El aislamiento es una **propiedad declarada del
validador**, no una convención de nombre de carpeta. Y se declara **por lo que
NO existe**: «no cross-job prefix filter exists» es una garantía de que nadie
puede barrer a través de dos trabajos. Es la misma disciplina que
`metrica-decide-la-conclusion.md` pide para una cifra —declarar la ceguera—
aplicada al direccionamiento.

**Nuestra diferencia.** Nuestra identidad **es** la ruta: `<slug>-<ISO>`. Un
slug mal escrito no lo detecta nadie, no hay validador de alcance, y no
declaramos ninguna garantía de aislamiento.

## 2. El registro de la ejecución: JSONL append-only con generación y posición

Una corrida de `Workflow` lleva `wf_<id>`, su `scriptPath` persistido, y un
**`journal`**. Lo que el ejecutable declara sobre él:

| Pieza | Qué implica |
|---|---|
| *«journal: skipping a malformed line»* | es **línea a línea** y tolera corrupción: una línea rota no invalida el archivo |
| `journalGeneration` | hay **generaciones**: el registro se puede rotar sin perder identidad |
| `journalEtag` | **concurrencia optimista** — dos escritores no se pisan en silencio |
| `journalPos` · `journalPosOrd` | **posición de lectura**: se puede reanudar desde donde se quedó |

**Nuestra diferencia.** Nuestras `outputs/` son archivos fechados sueltos. No
hay posición, ni generación, ni etag. Reanudar significa leerlos a ojo.

## 3. La reanudación: la caché va por la ENTRADA, no por la fecha

Verbatim: *«Completed `agent()` calls with unchanged (prompt, opts) return
their cached results instantly; only edited or new calls re-run.»*

La clave de caché es el par **`(prompt, opts)`** — ni un hash del archivo ni
una marca de tiempo. La unidad reanudable es **la llamada**, y su identidad es
su entrada.

**Nuestra diferencia.** Nuestro `reproducible` es una cadena con el comando.
Re-correr es manual y **total**: no hay reanudación parcial.

## 4. La salida durable: versionado optimista con `baseVersion`

Un Artifact se republica a la misma URL con su `baseVersion` rastreada, y un
escritor concurrente produce **conflicto**, no sobrescritura. Verbatim: *«The
tracked baseVersion is still sent; with `force:true` the server treats it as
informational and overwrites»*.

**Nuestra diferencia, y aquí ganamos:** nuestro destino es un commit. Git da
historia completa y no sólo la versión base.

## El reparto, eje por eje

| Eje | El cliente | Nosotros |
|---|---|---|
| Identidad | tupla `(namespace, scope)` **validada** | la ruta `<slug>-<ISO>`, sin validar |
| Aislamiento | **garantías declaradas** por lo que no existe | ninguna |
| Registro de ejecución | JSONL con generación, etag y **posición** | archivos fechados sueltos |
| Reanudación | caché por `(prompt, opts)`, **parcial** | re-correr entero, a mano |
| **Durabilidad** | muere con la sesión | **git** |
| **Premisa, métrica y ceguera** | no existe | **cinco claves obligatorias** |
| **Destino declarado** | no existe | **`destination`** |

Los tres últimos ejes son la razón de que este mecanismo exista. Los cuatro
primeros son **deuda nuestra con nombre**, y el cliente ya muestra la forma de
pagarla.

## Lo que conviene adoptar, y en qué orden

1. **La identidad validada.** El `manifest.json` puede llevar su `scope`
   —submódulo, iniciativa, tarea— y el gate validarlo, en vez de confiar en
   que el slug esté bien escrito.
2. **El registro con posición.** Un `journal.jsonl` por pieza, append-only,
   convierte las salidas sueltas en algo reanudable.
3. **La caché por entrada.** Si el `instrument` declara su entrada, se puede
   saber si hay que re-correr sin correr.

**Lo que NO se adopta es su efimeridad**, que es justo el defecto que este
mecanismo corrige.

*Métrica:* literales del volcado versionado de 2.1.251, con su contexto para
desambiguar el sentido; los conteos son líneas que contienen el literal.
*Ciega a:* el comportamiento real de cada mecanismo — un literal declarado no
prueba un mecanismo cableado; y a los namespaces que el cliente construya sin
literal.
