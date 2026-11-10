# Admisión de almacenamiento para los gates (2026-11-10)

## Incidente

Durante `ci-multidb` sobre `8f69391c` el disco de la sesión llegó a 37 MiB
libres. Un `git worktree add` falló a medias, un `cd` posterior no se
ejecutó y un `sed` de una medición exploratoria se aplicó al árbol principal;
se invirtió con el mismo `sed` y `git diff` quedó vacío (nada se commiteó).
Se retiraron cinco worktrees de revisiones ya commiteadas e integradas
(`gate-8b583110`, `gate-c9c7b545`, `gate-ee950202`, `gate-febd56b3`,
`gate-m2m`), unos 1.2 GB.

## Medición (09:30Z)

| Recurso | Valor | Instrumento |
|---|---|---|
| Techo real de escritura | **1 264 332 800 B** (1205.76 MiB) | `thyrox: bin/disk-headroom --ceiling-bytes` |
| Reserva del ext4 | 213.52 GiB, `resv_strict`: inalcanzable incluso para root | `bin/disk-headroom` (sale 3, `RESERVA_INALCANZABLE`) |
| Borrados y abiertos | 0 MiB | ídem |
| Inodos | 10 % usados (1 598 547 de 16 777 216) | `df -i /` |
| PostgreSQL | 1.4 GiB (`base` 1201 MiB, `pg_wal` 177 MiB) | `du` sobre `/var/lib/postgresql/16/main` |
| `max_wal_size` / `min_wal_size` | 1 GB / 80 MB | `SHOW` |
| Scratchpad | 647 MiB, de ellos 228 MiB el worktree del gate vivo | `du -sh` |
| `/tmp/pytest-of-root` | 18 MiB | `du -sh` |
| Caché de `uv` | 738 MiB, compartida por `uv run`: no se toca | `du -sh` |

*Métrica:* bytes que el sistema de archivos admite escribir. *Ciega a:* el
pico de WAL de una ejecución que no se ha observado, y a escritores ajenos.

## Qué crece durante cada gate

- **Worktree cualificado:** unos 228 MiB por revisión.
- **`ci-multidb`** (`scripts/run_multidb_isolation.py`): una base
  `orm_bootstrap_<hex>` (~43 MiB) y dos `company_*_db` por ejecución (~43 y
  ~24 MiB), unos 130 MiB en el pico. El guion borra al terminar lo que creó
  (`drop_created`, por diferencia con `companies_before` y comprobando el
  rol dueño).
- **WAL:** hasta `max_wal_size` (1 GB) entre checkpoints bajo escritura
  intensa. Es el componente que puede agotar el techo por sí solo.
- **Gate completo** (`pytest -n 4 --reuse-db`): reutiliza las bases `_gwN`;
  crecimiento observado despreciable salvo el log (~2 MiB).

## Bases residuales

Sin conexiones y fuera de la ejecución viva: `orm_bootstrap_276bbe3da956`,
`orm_bootstrap_b42418e0a4d4`, `company_11710386656870_db`,
`company_11710386656871_db`, `company_201103761692838_db`,
`company_201103761692839_db` (unos 214 MiB). Son de ejecuciones
interrumpidas anteriores; no se ha demostrado su propiedad en esta sesión,
así que **no se borran**. Como entran en `companies_before`, la limpieza de
cada ejecución nueva tampoco las toca.

## Regla de admisión

1. Nunca dos `ci-multidb` a la vez (comparten servidor y WAL).
2. Antes de un gate, retirar el worktree del gate anterior una vez copiada
   su evidencia (`record.json`, logs) fuera de él.
3. Reservar con el mecanismo del Provider,
   `thyrox: bin/resource_admission disk-admit --need-bytes N --owner <gate>`.
   El suelo por defecto (`THYROX_DISK_ADMISSION_FLOOR_MB`, 2048) supera el
   techo de esta sesión, así que se declara por ejecución a partir de lo
   medido: worktree 240 MiB + pico de `ci-multidb` 140 MiB = `N` 380 MiB, y
   suelo 300 MiB para el WAL por encima de lo ya presente. Con el techo
   actual (1205 MiB) eso admite **un** gate a la vez y ninguno con dos
   worktrees vivos.
4. Si el techo cae por debajo de `N` + suelo, el gate se difiere; los
   procesos vivos terminan.

## Veredicto recuperado de `ci-multidb` sobre `8f69391c`

- Worktree `gate-8f69391c` (revisión `8f69391c980ae45b0596888d453171462c2e6b48`),
  PID 32021/32045/32049, base desechable `orm_bootstrap_384fa3b20c8e`.
- `check_ci_database` exit 0; `pytest` exit 0: **5 passed** en 2078.84 s
  (`pytest_seconds` 2104); `EXIT=0` del guion.
- `dropped: true`; `dropped_companies: []`; `companies_before` y
  `companies_left` iguales: las cuatro `company_*_db` residuales previas,
  intactas.
- El incidente de disco (~09:13-09:18Z) cayó dentro de la ejecución: el log
  de PostgreSQL no registra ningún error de espacio (`grep -i "no space\|
  could not write\|could not extend\|PANIC"` sobre
  `/var/log/postgresql/postgresql-16-main.log`: sólo `FATAL role "root" does
  not exist` de sondeos), las cinco pruebas asentaron y la limpieza terminó.
  Se acepta el resultado.
- Evidencia copiada fuera del worktree antes de retirarlo:
  `$S/evidence-ci-multidb-8f69391c/` (`record.json` sha256 `a525b2f32c651e19…`,
  `junit_isolation.xml`, logs, muestreo de almacenamiento).

Muestreo de almacenamiento cada 15 s desde las 09:32Z hasta el final (33
muestras): `pg_wal` constante en **177 MiB** (el pico de WAL no creció en la
parte muestreada), `base` con pico de **1240 MiB** (+~90 MiB sobre el
reposo), mínimo libre **1161 MiB**. Tras retirar el worktree: 1517 MiB
libres.

## Lo que esta regla no cierra

El pico de WAL por encima de 300 MiB no está medido. Se mide durante el
siguiente `ci-multidb` con muestreo de `pg_wal`; si supera el suelo, la regla
se corrige con esa cifra.
