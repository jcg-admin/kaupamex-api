# Identidad de la F2 en ejecución: revisión `29285b00`

Registrado el 2026-11-17T22:23:39Z, con la F2 en curso (71 %).

| Dato | Valor | Comando |
|---|---|---|
| proceso | pid 3654, `full-batch.sh`, iniciado 2026-11-17 22:16:03 UTC | `ps -o pid,lstart,cmd` |
| commit bajo prueba | `29285b00`, confirmado 22:15:39 UTC | `git log --format='%h %cI'` |
| árbol del commit | `f433b2e25e5db3ebde29e7fcd3418b6ab9f3ad08` | `git rev-parse '29285b00^{tree}'` |
| commit posterior | `0f31b25a`, 22:17:38 UTC: sólo `designs/set-null-ondelete-block-d.md` | `git diff --stat 29285b00 HEAD` |
| código frente a `29285b00` | idéntico: 0 archivos fuera de `scripts/workbench` | `git diff --name-only 29285b00 -- . ':!scripts/workbench'` |
| árbol de trabajo | limpio | `git status --short` |

## El nombre del log no identifica la revisión

El log se escribe en `f2-ed74f56d.log` del scratchpad: el nombre viene de
una variable de sesión fijada para una F2 anterior y no se actualizó. El
archivo se truncó al lanzar (redirección `>`), así que su contenido es sólo
de esta ejecución; la fecha de creación del archivo (20:06 UTC) es la de la
F2 anterior y no la de su contenido. Para la recogida se usa el alias
`f2-29285b00.log` y la evidencia se persiste con la revisión `29285b00`
como argumento explícito de `persist_gate_evidence.py`.

*Métrica:* hora de inicio del proceso frente a la de los commits, y la
diferencia de árbol.
*Ciega a:* una edición del árbol hecha y deshecha durante la ejecución; la
sesión no hizo ninguna, y `git status` vacío lo confirma sólo en el momento
de medir.

Corrección de método: el nombre del log se deriva de `git rev-parse
--short HEAD` al lanzar, no de una variable heredada.
