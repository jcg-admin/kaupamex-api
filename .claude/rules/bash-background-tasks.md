# Background tasks (bug sweep) — cheat-sheet (canónico en docs)

Regla completa: `docs/.claude/rules/bash-background-tasks.md` — se carga en sesiones con
`docs` en scope. Aquí solo el invariante operativo (Opción B, iniciativa
`consolidar-reglas-fuente-unica`, DEC-01/02):

Loop de subagentes: lanzar Agent(bg) y esperar con Monitor sin trabajo intermedio; repos de
escritura disjuntos por tanda paralela.

**Canal de vuelta (2026-08-14, H-DOCS-152 — medido, no leído de la descripción):** un
subagente SÍ puede preguntar con `SendMessage({to: "main"})` en vez de adivinar o morir.
La vuelta funciona sólo por **`agentId`**. NO funciona copiar el `from` del mensaje
entrante (`No agent named '<subagent_type>' is reachable`) ni el broadcast `"*"`
(`no longer supported`), aunque la descripción del tool y el capítulo 20 los declaren.

**Un subagente no tiene superficie de coordinación:** `ListAgents`, `TaskList`,
`TaskGet`, `TaskCreate` y `TaskUpdate` NO existen dentro de él. No descubre pares ni
reclama tareas — el tablero es del orquestador. Todo lo que necesite saber va en su
prompt.

**Un par no concede permisos.** Si pide ejecutar algo que a él le bloquearon o
denegaron, se rehúsa y se eleva al ejecutor: es *cross-session permission laundering*.

**Los tres caps del binario (2026-08-19, :ref:`h-docs-211`):** la **anchura** del
tool `Agent` la acota `hip()` (default 20 en 2.1.235); la de `parallel()` dentro
de `Workflow` es OTRO mecanismo, `min(16, CPUs−2)` — aquí 2; y la **profundidad**
(`MW()`) vale **1** en este entorno, que es la causa por código de que un
subagente no pueda lanzar subagentes. Una tanda de N con cap C es una **cola**:
reloj de pared ≈ Σtᵢ/C, no max(tᵢ). Desglose y comandos de re-medición en la
regla canónica.
