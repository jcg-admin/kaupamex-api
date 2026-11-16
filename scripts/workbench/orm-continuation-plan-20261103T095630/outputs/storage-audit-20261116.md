# Auditoría de almacenamiento — VM-x2hokp

Medido el 2026-11-16T20:12:57, en sólo lectura salvo la retirada de §8. Gate activo durante
toda la auditoría: `ci-multidb` sobre `a3723a61`
(`outputs/gates/ci-multidb-a3723a61/`), sin tocar sus procesos, su árbol,
sus bases ni su directorio.

## 1. El sistema de archivos y lo que `df` mide

Una sola partición: `/dev/vda` ext4 montado en `/`; `/tmp`,
`/var/lib/postgresql` y `/home/user/kaupamex-api` están en ella
(`findmnt -T`). `df -hT`: 252G de tamaño, 38G usados, 924M disponibles.
La diferencia no es disco lleno: las opciones de montaje llevan
`resv_strict,resuid=65534,resgid=65534`, una reserva que sólo ese uid puede
usar. El disponible es la **asignación de la sesión**, y lo que se borra
vuelve a ella. Inodos: 10 % (1 514 079 de 16 777 216).

*Métrica:* `df`, `findmnt`, `du -x` con `sudo`.
*Ciega a:* bloques de archivos borrados y aún abiertos, que `du` no ve.

## 2. Consumo por directorio (`du -xhd1`)

| Ruta | Tamaño | Clase |
|---|---|---|
| `/home/user/odoo-tools` | 19G | referencia de sólo lectura — no se toca |
| `/home/user/thyrox` | 5.1G | proveedor — no se modifica desde esta VM |
| `/usr`, `/opt` | 4.8G, 2.4G | sistema |
| `/root` | 3.1G | cachés de herramientas: `.cache/uv` 738M (la caché **activa** de uv, que usa el gate), `.bun` 919M, `.rustup` 624M, `.claude` 394M |
| `/var/lib/postgresql` | 1.5G | 30 bases, §3 |
| `/home/user/kaupamex-docs` | 1.4G | otro repositorio |
| `/home/user/kaupamex-api` | 740M | este repositorio (árbol versionado 204 MB) |
| `/tmp` | 729M | §4 |

## 3. PostgreSQL (1.5G, 30 bases)

| Base | Propietario | Tamaño | Sesiones |
|---|---|---|---|
| `orm_x2hokp_qa_gw3` | orm_x2hokp | 76 MB | 0 |
| `orm_x2hokp_qa_gw1` | orm_x2hokp | 75 MB | 0 |
| `orm_x2hokp_qa_gw2` | orm_x2hokp | 70 MB | 0 |
| `orm_x2hokp_qa_gw0` | orm_x2hokp | 62 MB | 0 |
| `orm_x2hokp_qa` | orm_x2hokp | 58 MB | 0 |
| `orm_x2hokp_t41_gw2` | orm_x2hokp | 53 MB | 0 |
| `orm_x2hokp_t41_gw0` | orm_x2hokp | 53 MB | 0 |
| `orm_x2hokp_dev_gw1` | orm_x2hokp | 50 MB | 0 |
| `orm_x2hokp_t41_gw1` | orm_x2hokp | 50 MB | 0 |
| `orm_x2hokp_t41_gw3` | orm_x2hokp | 50 MB | 0 |
| `orm_bootstrap_e8ebda1641f3` | orm_x2hokp | 49 MB | 1 |
| `orm_x2hokp_preserve` | orm_x2hokp | 48 MB | 0 |
| `orm_bootstrap_12769386391b` | orm_x2hokp | 48 MB | 0 |
| `orm_x2hokp_dev_gw0` | orm_x2hokp | 46 MB | 0 |
| `orm_x2hokp_dev_gw3` | orm_x2hokp | 46 MB | 0 |
| `orm_x2hokp_dev_gw2` | orm_x2hokp | 43 MB | 0 |
| `company_201103761692838_db` | orm_x2hokp | 43 MB | 0 |
| `company_11710386656870_db` | orm_x2hokp | 43 MB | 0 |
| `orm_x2hokp_dev` | orm_x2hokp | 43 MB | 0 |
| `orm_bootstrap_b42418e0a4d4` | orm_x2hokp | 43 MB | 0 |
| `orm_bootstrap_276bbe3da956` | orm_x2hokp | 43 MB | 0 |
| `orm_x2hokp_probe` | orm_x2hokp | 40 MB | 0 |
| `company_122020071908891_db` | orm_x2hokp | 38 MB | 0 |
| `company_49412820869611_db` | orm_x2hokp | 31 MB | 1 |
| `orm_refproc_test_orm` | orm_x2hokp | 30 MB | 0 |
| `company_201103761692839_db` | orm_x2hokp | 25 MB | 0 |
| `orm_refproc_contract` | orm_x2hokp | 21 MB | 0 |
| `company_11710386656871_db` | orm_x2hokp | 20 MB | 0 |
| `template1` | postgres | 7567 kB | 0 |
| `postgres` | postgres | 7511 kB | 1 |

Clasificación:

- **Activas, del gate en curso** (declaradas en
  `ci-multidb-a3723a61/intent.json`, con sesión abierta):
  `orm_bootstrap_e8ebda1641f3`, `company_49412820869611_db`. Las retira el
  propio gate al escribir `record.json`.
- **Pendientes de conciliación** (propiedad no demostrable, ya clasificadas así
  en `outputs/conciliation-20261113.md`): `orm_bootstrap_12769386391b`,
  `orm_bootstrap_276bbe3da956`, `orm_bootstrap_b42418e0a4d4`,
  `company_122020071908891_db`, y las familias `orm_x2hokp_t41_*`,
  `orm_x2hokp_dev*`, `orm_x2hokp_preserve`, `orm_x2hokp_probe`,
  `orm_refproc_*`. No se borran.
- **Heredadas por todo gate, no compartidas por diseño** (corregido en §11):
  `company_11710386656870_db`, `company_11710386656871_db`,
  `company_201103761692838_db`, `company_201103761692839_db` aparecen en
  `companies_before` **y** `companies_after` de 33 registros porque cada gate
  posterior las encontró y, por diseño, no toca lo que ya existía. No son
  desechables mientras su propiedad no se demuestre.
- **De las pruebas**: `orm_x2hokp_qa` y `orm_x2hokp_qa_gw0..3` (las de
  `--reuse-db` y `-n 4`).

No hay ninguna base desechable **comprobada** fuera de las del gate activo.

## 4. `/tmp` (729M)

| Ruta | Tamaño | Clase |
|---|---|---|
| `/tmp/claude-0/.../0390150a…/scratchpad` | 489M (antes de §8) | esta sesión |
| `  …/scratchpad/uvcache` | 191M | C — caché de uv creada el 2026-11-06; 4679 de 6055 archivos (160 MB) son enlaces duros con `refenv`, así que retirarla libera ~21 MB |
| `  …/scratchpad/refenv` | 179M | A — entorno de la referencia que usan los diferenciales (`reference-environment-isolated-20261106T071536/README.md:87`) |
| `  …/scratchpad/*.log`, `*.sqlite3` | ~235M | B/D — logs de suites y copias de stores **únicos**: no están en el banco. Se conservan |
| `  …/scratchpad/multidb-nid.log` | — | A — abierto por el gate (`lsof`) |
| `/tmp/pytest-of-root` | 18M | A — `basetemp` de pytest, en uso por el gate |
| `/tmp/tmp*`, `claude-code-*.diag.log`, otros `claude-0/*` | <10M | D — otras sesiones, propietario no demostrado |

## 5. Git

- Un solo worktree: `/home/user/kaupamex-api` en
  `feature/vm-x2hokp-orm-root`. No hay copias físicas adicionales.
- `git count-objects -vH`: 20 764 objetos sueltos (161.7 MiB) y 2 paquetes
  (88.9 MiB), 0 basura. Un `git repack -d` (sin `-a`, sin poda) empaquetaría
  los alcanzables y retiraría sólo los sueltos ya empaquetados; se aplaza a
  después del gate.
- Ramas con commits que **ninguna** remota contiene: `local/adopt-schema-hooks-candidate` (1),
  `local/fk-producers` (1), `local/init-alias-candidate` (1),
  `local/init-overrides-candidate` (1), `local/logaccess-a-candidate` (1),
  `local/logaccess-c-candidate` (2). Se conservan: son referencias, no ocupan
  una copia.
- `feature/vm-x2hokp-orm-root` va 3 commits por delante de su remota
  (`a3723a61`, `9d1f1adf`, `e27c299d`): **comprometidos, no publicados**.
  Se publican al cerrar `ci-multidb`.

## 6. Evidencia no publicada

- Los 3 commits de §5.
- `outputs/gates/ci-multidb-a3723a61/`: lo escribe el gate en curso.

## 7. Qué puede retirarse con seguridad

Sólo lo que es copia exacta de evidencia ya versionada, de esta sesión y sin
proceso que lo use. Todo lo demás —bases sin propietario, logs únicos, el
entorno de referencia, cachés activas, el proveedor y la referencia— se
conserva.

## 8. Retirada efectuada

134 archivos del scratchpad de esta sesión cuyo `sha256` es idéntico a un
archivo del banco presente en `HEAD` (verificado otra vez archivo por
archivo justo antes de retirar, y ninguno abierto según `lsof`):
4 729 154 bytes. Disponible antes 961 753 088, después 967 065 600: **5 312 512
bytes** recuperados.

## 9. Conclusión medida

El espacio que puede liberarse sin riesgo hoy es marginal (~5 MB hechos, ~21 MB
de `uvcache` y lo que devuelvan `git repack -d` y el cierre del gate). Lo que
ocupa de verdad es la referencia (19G), el proveedor (5.1G), cachés activas de
herramientas y bases sin propietario demostrado. Mientras la conciliación de
§3 no se cierre, no se admite otro gate pesado en paralelo; el trabajo de
diseño y las pruebas focalizadas sobre la base QA ya creada siguen siendo
viables.

## 10. Ciclo de vida: lo que ya existe y lo que falta

Ya existe, y se reutiliza (`designs/storage-admission.md`): la admisión de
disco del gate (`thyrox: bin/resource_admission disk-admit`, con su piso), el
techo real medido con `bin/disk-headroom`, y la intención declarada **antes**
de crear bases (`intent.json` de `scripts/run_multidb_isolation.py`), que es
lo que permite a `--reclaim` retirar sólo lo propio de una ejecución
interrumpida. Medido el 2026-11-10: la reserva `resv_strict` es inalcanzable
incluso para root, la misma conclusión de §1.

Lo que esta auditoría encontró sin ciclo de vida: los logs de suite que el
scratchpad acumula. `persist_gate_evidence.py` copia el log al banco y lo
versiona, pero la copia del scratchpad queda; 134 de ellas eran duplicados
exactos. El paso MARK RECLAIMABLE que su cabecera nombra no se ejecuta sobre la
fuente. Sucesor: `gate-evidence-scratch-reclaim-0485`.

## 11. Conciliación de las bases históricas (2026-11-16T20:20:31)

Fecha de creación de cada base (`mtime` de `base/<oid>/PG_VERSION`), en
sólo lectura:

| Creada | Base |
|---|---|
| 2026-11-09 19:20:13 | `orm_bootstrap_b42418e0a4d4` |
| 2026-11-09 19:31:11 | `company_201103761692838_db` |
| 2026-11-09 19:46:21 | `company_201103761692839_db` |
| 2026-11-10 01:05:40 | `orm_bootstrap_276bbe3da956` |
| 2026-11-10 01:16:43 | `company_11710386656870_db` |
| 2026-11-10 01:30:16 | `company_11710386656871_db` |
| 2026-11-12 23:38:30 | `orm_bootstrap_12769386391b` |
| 2026-11-13 00:18:17 | `company_122020071908891_db` |

Cada `orm_bootstrap_*` va seguido, 11 a 40 minutos después, de sus bases
`company_*`: es la forma de una ejecución de `run_multidb_isolation.py`
(base de prueba y luego las empresas que aprovisiona). Son **tres ejecuciones
interrumpidas** anteriores al registro de intención (`intent.json` aparece por
primera vez en `ci-multidb-provision-e9fb9b5b`, 2026-11-13 20:18), y por eso
`--reclaim` no puede reclamarlas. La primera ya estaba documentada con su
causa en `outputs/residual-databases-20261109.md` (reclamo del contenedor) y
lleva **directiva del ejecutor de no eliminarla**.

Estado: **conciliadas por inferencia** (nombre que sólo forma ese guion, rol de
esta VM, secuencia temporal), **no demostradas**. Ninguna se borra. Las de
`orm_x2hokp_probe`, `orm_x2hokp_dev*`, `orm_x2hokp_t41_*`,
`orm_refproc_*` y `orm_x2hokp_preserve` (2026-11-02 a 2026-11-11) son bases
de trabajo de esta VM sin registro de ciclo de vida; siguen pendientes.

## 12. Compresión verificada del scratchpad

Los logs y copias SQLite **únicos** —no reconstruibles: son instantáneas de
ejecuciones y del store— se comprimieron en lugar de retirarse. Cada archivo
cerrado (más de un día sin modificar, ningún proceso abierto según `lsof`)
se comprimió con `gzip -9`; el original se retiró sólo si `gzip -t` pasaba
y el `sha256` de lo descomprimido coincidía con el del original. 30 archivos,
140 605 350 bytes a 19 543 334. Disponible antes 979 689 472, después
1 100 677 120: **120 987 648 bytes recuperados**, sin pérdida de información.
El manifiesto (nombre, tamaño, `sha256` original, archivo comprimido) está en
`outputs/scratch-compression-manifest-20261116.tsv`. No se versionan los
archivos: son copias locales de trabajo, de contenido no evaluado para
publicarse.

Total recuperado comprobado: 5 312 512 (§8) + 120 987 648 = **126 300 160
bytes**.
