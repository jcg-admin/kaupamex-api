# ReAct Verification Gate

Creado: 2026-05-29T03:13:51
Actualizado: 2026-05-29T03:33:54
Referencia: Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models", ICLR 2023.
Fuente local: `/tmp/references/ReAct/`

## El problema que esta regla resuelve

El agente tiene un patrón defectuoso documentado empíricamente:

1. Ejecuta una acción
2. **Asume** que tuvo éxito
3. Reporta como hecho

El paso 2 no debe existir. El defecto no es de redacción ("verifica antes de
reportar") sino de ciclo de decisión: el agente salta la sub-etapa de
Evaluation y trata el resultado *esperado* de una acción como si fuera su
resultado *real*.

## Invariante fundamental

**Ninguna afirmación de estado puede provenir de la distribución del LLM.**

Una afirmación de estado es cualquiera de estas: "hecho / creado / completado",
un conteo (46/46), un timestamp, un hash, una ruta, la existencia de un archivo,
o su contenido.

Toda afirmación de estado debe derivarse de una `Observation`: la salida literal
de una herramienta ejecutada **en este turno**.

Corolario operativo: si no se ejecutó la `Observation`, el estado es
DESCONOCIDO, no "éxito". El resultado esperado nunca es evidencia del resultado
real.

El ciclo obligatorio es:

```
Thought N → Action N → Observation N → Thought N+1
```

No se puede escribir `Thought N+1` — ni reportar, ni marcar done, ni escribir un
valor, ni proponer la siguiente acción — sin haber recibido `Observation N` de
una acción real ejecutada en este turno.

## 1. Clasificación de toda acción

Toda acción cae en una de dos clases:

- **Mutación** — cambia el mundo: `Write`, `Edit`, `MultiEdit`, `bash` que
  escribe / borra / mueve, `git add` / `commit`, `mkdir`.
- **Afirmación de estado** — declara completitud, conteo, timestamp, hash, ruta,
  existencia o contenido.

El gate aplica a ambas clases. El alcance NO es "antes de reportar"; es
universal.

## 2. Gate de Observation (obligatorio)

Cada acción de **mutación** va seguida inmediatamente de una `Observation` que
verifique su efecto, ANTES de proponer la siguiente acción o reportar.

La `Observation` es un read-back real, no una suposición ni una relectura del
propio plan:

```
cat | ls | test -f | grep | wc -l | git status | git log -1 | git diff --stat
```

Incorrecto:

```
Thought: la tarea requería crear el archivo X
Action:  Write X
Action:  escribo "completado" en el progreso     ← sin Observation
```

Correcto:

```
Thought: la tarea requería crear el archivo X
Action:  Write X
Action:  test -f path/to/X && cat path/to/X
Observation: el archivo existe / el contenido es correcto
Action:  escribo "completado" en el progreso
```

Si la verificación falla o fue omitida: escribir `omitido` o `parcial`, nunca
`completado`.

## 3. Regla de citación auditable

Toda afirmación de estado debe ir acompañada del comando ejecutado y su salida
literal. Sin salida citada, la afirmación es inválida y no se emite.

Esto hace el gate verificable por un tercero, no por intención declarada: el
ejecutor puede revisar el comando y la salida sin confiar en la palabra del
agente.

## 4. Valores derivados del entorno

Timestamps, conteos, hashes y rutas se obtienen ejecutando el comando, nunca se
escriben de memoria:

- Timestamps → `date -u +"%Y-%m-%dT%H:%M:%S"`  (ver `timestamps-iso8601-obligatorios.md`, caso particular de esta regla)
- SHA de commit → `git rev-parse HEAD` / `git log -1 --format=%h`
- Conteo de tests → `pytest -q | tail -1`
- Número de líneas / archivos → `wc -l`, `find | wc -l`
- Estado / contenido de un archivo → `cat`, `grep`, `git diff --stat`

Un timestamp con `HH:00:00` o `MM:00:00` sin `date -u` ejecutado es una
violación, no una coincidencia.

## 5. Learning actions con gate reforzado

Escribir a memoria long-term es una **learning action**: el error persiste y
contamina ciclos futuros. Aplica a:

- `progreso-<slug>.rst`
- el SMD (valores de baseline, SHAs, contadores)
- `lecciones-aprendidas/`

En learning actions el observable se verifica ANTES de comprometer la
información, no después. Un dato erróneo en memoria long-term se recupera como
verdad en sesiones posteriores.

## 6. Auto-escalación por metareasoning

En contextos de alto riesgo la verificación pasa de muestreo a **exhaustiva**
(archivo por archivo) y se ejecuta tras cada `Write` individual, no al final del
batch. El agente declara explícitamente cuando entra en modo exhaustivo.

Contextos de alto riesgo:

- Batch de `Write` / `Edit`.
- Subagentes paralelos que sintetizan salida acumulada.
- Contexto largo (riesgo de compaction: el valor verificado en un turno
  temprano puede no sobrevivir a la compactación).
- Más de N archivos en una misma tarea.
- Cierre de iniciativas: marcar done, actualizar contadores, cambiar `:estado:`.

### 6-bis. La compactación NO conserva la evidencia — persistirla es la defensa

El paréntesis de arriba —*"el valor verificado en un turno temprano puede no
sobrevivir a la compactación"*— es correcto y se queda corto: dice que **puede**
no sobrevivir, sin decir **qué** sobrevive. Medido sobre el prompt de resumen
del ejecutable 2.1.258 (`XWo`), que obliga a nueve secciones:

- **Lo que es directiva sobrevive**, y es la única garantía textual del
  mecanismo. El prompt exige verbatim las directivas permanentes y las
  prohibiciones —*"operations that must not be performed, credential or secret
  handling rules"*— porque *"these MUST be preserved verbatim in the summary so
  they continue to apply after compaction"*.
- **Lo que es evidencia, no.** Una cifra medida a mitad de sesión pasa por la
  reescritura y puede volver como paráfrasis. El resumen no es compresión sin
  pérdida: es una reescritura guiada.

De ahí el criterio operativo, y **no es «no comprimir»**: apagar la
compactación no mueve el tope duro —se calcula sobre la ventana efectiva, no
sobre el umbral—, así que sólo quita el escalón de aviso y hace que el margen
reportado mienta. La defensa es **persistir**: un dato que importa va al `.rst`
o a `.claude/eventos/**` **antes** de que el contexto se llene. Es el nivel 4
de `niveles-de-retencion.md` —completitud percibida sin persistencia— aplicado
a la sesión en vez de a un subagente, y lo mismo que `build-logs.md` ya exige
para una prueba: el `.log` es tan durable como el contenedor.

Análisis completo, con el coste de los dos caminos en tokens equivalentes:
`docs: source/gestion/pm/docs/iniciativas/construir-harness-propio/`
`analisis-que-pasa-si-no-se-comprime-la-sesion.rst`.

## Señal de violación

Si en un turno aparece alguno de estos patrones sin un comando ejecutado
inmediatamente antes que lo produzca:

- Un timestamp con `HH:00:00` o `MM:00:00`
- Un conteo ("46/46", "1432/0/0") sin grep / pytest / wc que lo confirme
- Un SHA sin `git log` que lo muestre
- Un "completado" sin verificación del artefacto

es una violación de este gate. Corregir antes de reportar y registrar el
episodio según `memoria-episodica-fallos.md`.
