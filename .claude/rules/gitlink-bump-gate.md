# Gitlink Bump Gate — Obligatorio tras cada commit en submódulo

Creado: 2026-05-30T06:39:10
Origen: reincidencia documentada en L-004 (2 fallos en la misma sesión)

## El problema que esta regla resuelve

El agente comitea en un submódulo (api, db, docs, server, ui), pusheqa,
y declara "publicado" — sin bumpear el gitlink del superproyecto. Desde
el superproyecto, el commit del submódulo no existe. El estado del repo
es inconsistente.

L-004 (2026-05-29) documentó el primer fallo. En el checkpoint siguiente
(CP2) el agente reincidió exactamente en el mismo error, inmediatamente
después de registrar la lección. La lección escrita no previene la
reincidencia. Solo un gate ejecutable integrado en el flujo lo hace.

## La regla

**Después de cada `git push` en cualquier submódulo, ejecutar el gate
ANTES de cualquier otra acción o reporte:**

```bash
# Desde el superproyecto (kaupamex/)
git -C .git/modules/<submodulo> fetch <ruta-local-submodulo>
git -C <submodulo> checkout <hash-del-tip>
git add <submodulo>
git diff --staged   # debe mostrar index <hash-viejo>..<hash-nuevo> 160000
git commit -m "Bump <submodulo> to <hash> (<descripcion>)"
git push -u origin <rama>
git ls-tree HEAD <submodulo>
# Output esperado: 160000 commit <hash-real>   <submodulo>
```

**La afirmación "publicado" / "completo" / "cerrado" NO puede emitirse
hasta que `git ls-tree HEAD <submodulo>` devuelva el hash esperado.**

## Submódulos del superproyecto kaupamex

| Submódulo | Ruta local |
|-----------|------------|
| `api`     | `/home/user/kaupamex-api` |
| `db`      | `/home/user/kaupamex-db` |
| `docs`    | `/home/user/kaupamex-docs` |
| `server`  | `/home/user/kaupamex-server` |
| `ui`      | `/home/user/kaupamex-ui` |

## Gate mínimo verificable (no omitible)

```bash
git ls-tree HEAD <submodulo>
# 160000 commit <hash>   <submodulo>
# Si el hash no coincide con el tip pusheado → NO declarar publicado.
```

Citar la salida de `git ls-tree` en el turno. Si no se cita, el estado
es DESCONOCIDO según `react-verification-gate.md`.

## Cuándo aplica

- Después de CADA `git push` en cualquier submódulo.
- En contextos de HALT, checkpoint (CP1/CP2/CP3...), o cierre de tarea.
- Aunque el push sea "solo documentación" o "trivial".

## Precondición: el superproyecto tiene que estar en la sesión

**Directiva del ejecutor 2026-08-07T19:38:44.** El superproyecto **ya no se
trabaja**: no se estaba operando correctamente y el repo vivía siempre en un
mismo estado. Queda **ausente por decisión** desde el arranque de esta sesión,
y sigue así hasta que se cargue o se inicie otra conversación con él.

Medido en el mismo turno: `ls -d /home/user/kaupamex` → *No such file or
directory*; el árbol tiene los **cinco clones hermanos** (`kaupamex-api`,
`-db`, `-docs`, `-server`, `-ui`) más `odoo-tools` y `-progress`.

Consecuencia operativa, y es la mitad que faltaba de esta regla:

- **Con el superproyecto en la sesión** → la regla aplica entera, sin cambios.
  Nació de dos fallos reales en la misma sesión (L-004), y esos siguen siendo
  posibles.
- **Sin él** → el bump **no se puede hacer ni verificar**. Entonces no se
  declara "publicado y bumpeado" (sería una afirmación de estado sin
  `Observation`), pero **tampoco se bloquea el push del submódulo**: el push
  es completo en su propio repo. Se dice explícitamente que el gitlink queda
  **DESCONOCIDO por ausencia del superproyecto**, y se sigue.

Lo que **no** es válido en ninguno de los dos casos: callar. Un push de
submódulo sin mención del gitlink se lee como bump hecho, que es exactamente
el defecto que L-004 registró dos veces.

**Por qué se repunta y no se retira.** `principio-aprender-haciendo` Cláusula 2
da dos desenlaces para una regla heredada que no se sostiene: repuntar a lo que
existe, o retirar. Aquí la regla **sí** se sostiene — lo que cambió es su
**precondición**, no su contenido. Retirarla dejaría el proyecto sin defensa el
día que el superproyecto vuelva; dejarla sin esta sección la convierte en una
orden incumplible, que es cómo una regla se vuelve ruido que nadie obedece.

## Cuándo NO aplica

- Commits directamente en el superproyecto (no crea gitlink pendiente).
- Operaciones de solo lectura (grep, cat, git log).

## Historial de fallos (retrieval episódico)

Ver `lecciones-aprendidas/gate-gitlink-declarado-publicado-sin-bump-2026-05-29.rst`
(L-004) para los dos episodios documentados: ADR-012 v3.0.0 y CP2 de UC-CAT-14.
