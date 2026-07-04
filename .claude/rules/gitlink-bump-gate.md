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
# Desde el superproyecto (e-comerce/)
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

## Submódulos del superproyecto e-comerce

| Submódulo | Ruta local |
|-----------|------------|
| `api`     | `/home/user/e-comerce-api` |
| `db`      | `/home/user/e-comerce-db` |
| `docs`    | `/home/user/e-comerce-docs` |
| `server`  | `/home/user/e-comerce-server` |
| `ui`      | `/home/user/e-comerce-ui` |

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

## Cuándo NO aplica

- Commits directamente en el superproyecto (no crea gitlink pendiente).
- Operaciones de solo lectura (grep, cat, git log).

## Historial de fallos (retrieval episódico)

Ver `lecciones-aprendidas/gate-gitlink-declarado-publicado-sin-bump-2026-05-29.rst`
(L-004) para los dos episodios documentados: ADR-012 v3.0.0 y CP2 de UC-CAT-14.
