# Memoria Episódica de Fallos del Gate

Creado: 2026-05-29T03:33:54
Actualizado: 2026-05-29T10:13:50
Referencia: Shinn et al., "Reflexion: Language Agents with Verbal Reinforcement
Learning", NeurIPS 2023 (citado en CoALA, Sumers et al. 2024, como memoria
episódica de fallos).
Regla hermana: `react-verification-gate.md`.

## El problema que esta regla resuelve

El gate de verificación atrapa una discrepancia en el turno (afirmé X, la
`Observation` muestra Y), pero sin registro la lección se pierde y el ciclo se
repite en la siguiente sesión. CoALA describe esto como una **learning action**:
comprometer el episodio fallido a memoria long-term para que esté disponible
como retrieval en ciclos futuros.

## La regla

**Cada vez que el gate de verificación detecta una discrepancia, registrar el
episodio como una lección antes de cerrar el turno.**

No se inventa un formato nuevo. El proyecto ya tiene mecanismo de retrospectiva:
se escribe una lección en `lecciones-aprendidas/` usando el formato RST
con frontmatter `:categoria:` y `:condicion:` fijos. Esta regla solo fija cómo
se llena para un fallo del gate, de modo que sea recuperable.

## Trigger

Se registra cuando, y solo cuando, se cumple:

- El agente emitió (o estuvo a punto de emitir) una afirmación de estado, y
- la `Observation` posterior contradice esa afirmación.

No se registra una verificación que pasó sin discrepancia. Solo episodios donde
la evaluación falló.

## Mapeo al template de lección

Frontmatter RST (`:campo: valor`):

- `:categoria: Metodología`
- `:condicion: Fallo del ReAct verification gate — afirmación de estado sin Observation soporte`

La `condicion` se mantiene literal e idéntica en todos estos episodios: es la
clave de retrieval. Un grep por esa cadena devuelve todos los fallos del gate.

Secciones del archivo RST, llenadas así:

- **Contexto** — la tarea y sus condiciones; declarar si era contexto de alto
  riesgo (batch, subagentes paralelos, contexto largo, cierre de iniciativa).
- **Qué Pasó** — `outcome_esperado` vs `outcome_observado`: lo que el agente
  asumió, y la salida literal de la `Observation` que lo contradijo. La salida
  literal es obligatoria; sin ella la lección es descriptiva, no accionable.
- **Causa Raíz** — una de estas categorías de fallo:
  - salto de `Observation`
  - valor tomado de Semantic Memory ("los timestamps se ven así", "un Write
    suele tener éxito") escrito como si fuera el valor real del entorno
  - batch sin verificación exhaustiva
- **Solución Aplicada** — qué `Observation` debió ejecutarse y cuándo.
- **Regla** — formato "Cuando [condición], ejecutar [Observation] antes de
  [afirmación], porque [razón]".
- **Cuándo Aplica / Cuándo NO Aplica** — según el template.

## Retrieval (la mitad que cierra el loop)

El registro sin consulta no corrige nada. Antes de una tarea del mismo tipo
(misma `categoria` o mismo contexto de alto riesgo), el agente consulta los
episodios previos.

### Nota crítica: lecciones-aprendidas/ vive en el submódulo `docs/`

`lecciones-aprendidas/` está en `e-comerce-docs`, no en el árbol del
superproyecto. `docs/` es un submódulo (modo `160000`). Cualquier grep
desde el superproyecto **requiere el submódulo poblado**:

```bash
# Opción 1: desde el superproyecto (e-comerce/), submódulo poblado
git submodule update --init docs
grep -rl "Fallo del ReAct verification gate" \
    docs/source/gestion/pm/docs/lecciones-aprendidas/

# Opción 2: desde dentro del submódulo (e-comerce-docs/)
grep -rl "Fallo del ReAct verification gate" \
    source/gestion/pm/docs/lecciones-aprendidas/
```

El grep apunta específicamente a `docs/` para no confundirlo con los otros
cuatro submódulos (`api/`, `db/`, `server/`, `ui/`). Usar la ruta completa
evita que un grep amplio trate cinco submródulos distintos como una sola
busqueda.

La consulta es parte de la fase de Proposal: el agente entra a la tarea
sabiendo dónde falló antes.

## Primer episodio registrado (caso de prueba de la regla)

Fecha: 2026-05-29  
Archivo: `e-comerce-docs: source/gestion/pm/docs/lecciones-aprendidas/gate-fallo-git-ls-tree-submodulo-2026-05-29.rst`  
Causa raíz: valor de Semantic Memory escrito como estado verificado.  
Descripción: el agente afirmó "ruta verificada con `git ls-tree`" sobre
el superproyecto cuando `docs/` es un submódulo. `git ls-tree -r` sobre el
superproyecto devuelve solo el gitlink (`160000 commit d81bf8a... docs`),
nunca el contenido del submódulo. La afirmación no pudo derivarse del
comando citado.

## Verificación de aterrizaje (obligatoria antes de declarar registrado)

Tras escribir el episodio, ejecutar el MISMO grep de retrieval y
confirmar que devuelve el archivo recién creado:

```bash
# Opción 1: desde el superproyecto (e-comerce/), submódulo poblado
grep -rl "Fallo del ReAct verification gate" \
    docs/source/gestion/pm/docs/lecciones-aprendidas/

# Opción 2: desde dentro del submódulo (e-comerce-docs/)
grep -rl "Fallo del ReAct verification gate" \
    source/gestion/pm/docs/lecciones-aprendidas/
```

Si el grep no devuelve el archivo, el episodio está mal ubicado o mal
formateado y **NO está registrado** — corregir antes de cerrar el turno.
Citar la salida del grep en el turno. Esto cae bajo
`react-verification-gate.md` punto 5 (learning action: verificar el
observable antes de declarar hecho).

## Por qué no un log paralelo

Un esquema YAML aparte duplicaría el mecanismo de lecciones ya existente y
fragmentaría el retrieval. La memoria episódica de fallos es un caso particular
de lección, identificado por su `condicion` fija. Un solo lugar para buscar,
una sola convención que mantener.
