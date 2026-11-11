# Finalización de la evidencia de un gate

Diseño medido el 2026-11-11T01:16:36. Corrige el uso del scratchpad
(`/tmp/claude-0/.../scratchpad/`) como destino de la evidencia: es un
directorio temporal y no sirve como punto de recuperación.

## La brecha, medida

- `scripts/run_multidb_isolation.py` ya acepta el directorio de salida como
  argumento (`main(out_dir)`); `make ci-multidb` no se lo pasaba, así que el
  expediente caía en `test-results/multidb/`, que está en `.gitignore`
  (`.gitignore:22`) y vive **dentro del worktree del gate**: se perdía al
  retirarlo.
- El paso de recuperación copiaba el expediente al scratchpad. Ahí acabaron
  14 expedientes de ci-multidb y los logs de 3 gates completos y 2
  subconjuntos, sin índice, sin hash y sin relación con su unidad.
- Los scripts que lanzan los gates (`run-gate-multidb.sh`, la variante con
  anulación, `full-batch.sh` y las cadenas) también vivían sólo en el
  scratchpad.

## La corrección

| Pieza | TRAE / CONSTRUYE | Qué hace |
|---|---|---|
| argumento de `run_multidb_isolation.py` | **TRAE** | el productor ya escribe donde se le pide |
| `probes/gate-procedure/` | persistido | los scripts de gate llaman a `run_multidb_isolation.py` con su argumento de salida, `outputs/gates/ci-multidb-<revisión>[-null]` del árbol principal, en vez de a `make ci-multidb` |
| `probes/persist_gate_evidence.py` | CONSTRUYE | copia el expediente a `outputs/gates/<nombre>/` y añade su fila a `outputs/gates/index.tsv` con el hash de cada archivo; lo que el gate no registró queda como `-` |

Mismo banco (`orm-continuation-plan-*`), mismo juego de archivos que el
banco `multidb-isolation-disposable-database-*`. No hay banco nuevo ni base
de datos de evidencias.

## La secuencia

```text
EXECUTE → FINALIZE → PERSIST → VERIFY PERSISTENCE → MARK RECLAIMABLE → CLEANUP
```

1. **EXECUTE:** el gate se lanza con el directorio de salida apuntando al banco.
2. **FINALIZE:** al asentarse, `record.json` tiene la revisión, la base, el
   código de salida y la duración.
3. **PERSIST:** `persist_gate_evidence.py` indexa el expediente (o copia el
   log de una suite completa) con su resultado esperado y su limitación.
4. **VERIFY PERSISTENCE:** tras el commit, cada archivo se lee con
   `git show <commit>:<ruta>` y su hash se compara con `index.tsv`. Sin el
   scratchpad, sin el worktree.
5. **MARK RECLAIMABLE:** sólo lo que el paso 4 verificó.
6. **CLEANUP:** el worktree del gate y la copia temporal. Nunca una base de
   propietario desconocido.

## Desperdicio eliminado o reducido

| Desperdicio | Antes | Ahora |
|---|---|---|
| repetir una suite para recuperar evidencia perdida | la evidencia caía en un directorio que se borra con el worktree | el expediente cae en el banco; no hace falta repetir nada para recuperarlo |
| copias entre ubicaciones temporales | worktree → scratchpad → (nada) | worktree → banco, una vez |
| logs sin clasificar | 19 expedientes sueltos | `index.tsv`: revisión, base, salida, totales, esperado, observado, limitación y hashes |
| procedimiento irrecuperable | scripts de gate sólo en el scratchpad | `probes/gate-procedure/` versionado |

## Lo que no hace

- No registra la TASK, el settlement ni la aceptación del expediente. Ese
  vínculo vive en `outputs/line-reconciliation-20261110.md` y en
  `outputs/continuation.jsonl`. Publicar la evidencia no es aceptar el
  contrato.
- Los gates completos no tienen `record.json`: su revisión sale del árbol
  medido y su base son las `orm_x2hokp_qa_gw0..3`. Inicio y fin no se
  registraron (`-`).

## Por qué no se tocó el `Makefile`

Un parámetro `MULTIDB_OUT` en `make ci-multidb` era la forma más corta,
pero el `Makefile` es superficie protegida: su admisión exige cualificar los
verificadores (`--qualify-checkers`). La cualificación pasó fuera del hook y
falló dentro de él, con 7 de 99 pruebas. Esas pruebas crean repositorios git
propios y, con toda probabilidad, heredan el entorno git del hook. Como el
productor ya acepta el destino, llamarlo directamente evita la superficie
protegida sin perder nada. La falla de la cualificación dentro del hook
queda como observación de su propio arnés, sin diagnóstico cerrado.

## Frontera de recuperación antes de un gate largo (2026-11-11T01:48:18)

**Episodio.** El primer gate completo de `adopt_schema_hooks` corría sobre
el árbol de trabajo, con cambios sin commitear, y un reinicio del contenedor
lo cortó al 97 % (`uptime -s` 2026-11-11 01:33:03). El código sobrevivió en
el árbol, pero nada garantizaba que lo hiciera, y el gate no dejó veredicto.

**Corrección.** El repositorio prohíbe commitear mientras una suite corre
sobre esos mismos cambios, así que la revisión estable no puede ser un
commit de la rama antes del gate. Se usa una **referencia local de
snapshot**:

```text
índice temporal → git read-tree HEAD → git add <rutas> → git write-tree
→ git commit-tree -p HEAD → git update-ref refs/heads/local/<unidad>-candidate
```

No toca ni el índice real ni el árbol de trabajo, no es un commit de la rama
y no se publica. Fija el contenido exacto que el gate verifica, con sus
hashes, en el almacén de objetos del repositorio, que sobrevive a un
reinicio. Aplicado a `adopt_schema_hooks`: `local/adopt-schema-hooks-candidate`
= `8780c994`, los tres archivos con el mismo sha256 en el árbol y en el
snapshot.

**Secuencia de una unidad, desde ahora:** contrato → diseño persistido →
implementación → RED/GREEN → anulación → regresión focalizada → admisión
estática → **snapshot local con sus hashes** → gate completo → persistencia
del veredicto (`persist_gate_evidence.py`) → commit y publicación por
pathspec → settlement si corresponde → siguiente obligación.

**Un gate cortado se registra como interrumpido**, sin veredicto:
`status: interrupted`, `cause: container restart`,
`final_verdict: unavailable`, con su revisión, su punto de corte y su
`boot_id` si se registró. No se repite sólo para probar que se cortó.

**Lo que no resuelve:** la ventana entre el último commit y el snapshot,
y un gate cuyo log vive en el scratchpad hasta que se persiste. La mejora
que cerraría la segunda, que el lanzador escriba directamente en
`outputs/gates/`, ya está en los scripts de `probes/gate-procedure/` para
el ci-multidb. Para el gate completo, `full-batch.sh` todavía escribe en el
scratchpad.
