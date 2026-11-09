# Operación: aviso de autoría, publicación y alcance de la verificación

Directiva del ejecutor 2026-11-09 (corrección operativa).

## 1. Origen del aviso «Unverified»

| Dato | Medido |
|---|---|
| `core.hooksPath` | `.githooks` (`.git/config`) |
| `user.name` / `user.email` | `jcg-admin` / `169318663+jcg-admin@users.noreply.github.com` (`.git/config`) |
| `commit.gpgsign` / `gpg.format` | `true` / `ssh` (`/root/.gitconfig`, del entorno) |
| Emisor del aviso | `~/.claude/stop-hook-git-check.sh`, registrado como hook `Stop` en `/root/.claude/launcher-settings.json` |

Es un **control del entorno de ejecución administrado**, no un hook de git del
repositorio: `.githooks/` no contiene esa regla. Su lógica (líneas 105-170)
marca como «Unverified» todo commit que no esté en ningún remoto y que no
tenga cabecera `gpgsig` **o** cuyo committer no sea `noreply@anthropic.com`,
porque la clave de firma del entorno está registrada a esa identidad.

Los commits de esta rama **sí están firmados**: `git cat-file -p HEAD` lleva
`gpgsig`. `%G?` da `N` sólo porque el entorno no configura
`gpg.ssh.allowedSignersFile` (el propio script lo documenta). El aviso es,
por tanto, de **identidad de la clave**, no de ausencia de firma: GitHub no
puede asociar la firma a `jcg-admin`.

No es un archivo de este repositorio ni de Thyrox, y no se modifica. La
identidad canónica la fija `git-author-identity.md` y no se cambia para
satisfacerlo. El aviso cesa por sí solo para los commits publicados, porque
el script sólo mira `HEAD --not --remotes`. Hacer que GitHub muestre los
commits como verificados exige registrar una clave de firma de `jcg-admin`
en su cuenta: decisión y acción del titular de la cuenta, fuera de esta
sesión.

## 2. Publicación y `check_pushed_branch.py`

`thyrox: src/verify/check_pushed_branch.py` (pre-push) rechaza un push cuyas
refs locales no incluyan la rama actual mientras ésta tenga commits sin
publicar. Su propósito es impedir el «Everything up-to-date» sobre la rama
equivocada. Un `git push origin <sha>:<rama>` no declara la rama actual y se
rehúsa, como está diseñado. No se debilita.

Consecuencia: en `kaupamex-api` se publica la rama completa cuando todas sus
unidades con código tienen su gate. `kaupamex-docs` se publicó el 2026-11-09
en `3e0d76bf7` (fast-forward, 19 commits, committer `jcg-admin`).

## 3. Aislamiento de multidb

`scripts/run_multidb_isolation.py` crea una base desechable propia
(`orm_bootstrap_<hex>`), pero ejecuta pytest con `cwd=ROOT` sobre el checkout
mutable y registra `git rev-parse HEAD`. Mientras corre, no se edita `src/`
ni `addons/`. Los commits que sólo tocan el Workbench no cambian el código
verificado; su revisión registrada se atribuye comparando el diff con la
revisión de la unidad.

Mejora disponible sin cambiar política: ejecutar los gates en un worktree
inmutable (`git worktree add <dir> <rev>`) con el entorno virtual del clon.
Queda como siguiente paso, medido antes de usarlo.

## 4. Alcance de la verificación

`thyrox: .claude/rules/alcance-de-la-suite.md` fija que la suite entera es
obligatoria sólo en tres casos: mecanismo transversal, cierre de bloque o
apertura de PR, o petición del ejecutor. Ejecutarla, con multidb, para
**cada** unidad era una práctica de esta sesión, no una regla. Desde ahora,
cada unidad lleva su matriz de impacto:

```
Changed symbols / Changed behavior / Direct consumers / Indirect consumers /
Required contract tests / Required regression tests / Required integration
gates / Previously valid evidence / Uncovered risks
```

- Nivel 1: contrato, RED/GREEN, anulación y estilo.
- Nivel 2: consumidores reales derivados por grep del símbolo.
- Nivel 3: suite completa y multidb sólo si el cambio es transversal sin
  cobertura suficiente, o en el corte de publicación de la rama.

`settle_item.py` exige sólo el `verify` de la unidad; ningún mecanismo de
Thyrox obliga a la suite completa por unidad. No hay cambio de Provider que
canalizar a VM-A por este punto.

## Worktree de gate: el clon se reconoce por su nombre y sus hermanos

Medido sobre `983f06bc` (2026-11-09): la suite de nivel 3 dio
`2 failed, 12288 passed, 5 errors`. Los 5 errores son los de
`test_multidb_isolation` que se repiten en todas las ejecuciones `-n 4`
anteriores (los cubre `make ci-multidb`, que salió `EXIT=0`). Los 2 fallos son
de `tests/unit/scripts/test_check_workbench.py` y vienen del sitio del
worktree, no del código:

- `thyrox: src/workbench/paths.py::workbench_dir` elige la clave por clon con
  `repo_of`, que recorta el prefijo `kaupamex-` derivado **por mayoría de los
  clones hermanos**. Un worktree en el scratchpad no tiene hermanos: su clave
  sale `THYROX_WORKBENCH_KAUPAMEX_API` (o `..._API_GATE_983F06BC` si el
  directorio no se llama `kaupamex-api`) y el `.env` no la declara.
- Sin `thyrox` como hermano, `check_workbench.thyrox_root()` rehúsa con exit 2.

Control: en el mismo worktree, `THYROX_ROOT=/home/user/thyrox
THYROX_CLONE_PREFIX=kaupamex-` da `20 passed`; sin el prefijo, los mismos 2
fallos.

Forma del worktree de gate desde ahora:
`git worktree add --detach $S/gate-<rev>/kaupamex-api <rev>`, con `src/.env` y
`.env` copiados, y el nivel 3 lanzado con `THYROX_ROOT=/home/user/thyrox
THYROX_CLONE_PREFIX=kaupamex-`.
