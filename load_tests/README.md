# Load tests — suite de performance (RNF-PERF)

Esqueleto de la suite de **load testing** con [Locust](https://locust.io)
que valida los SLO de performance del proyecto. Cierra los **153** AC-07
(performance/concurrencia) **a nivel de NFR** — la performance es un
requisito transversal, no se valida AC por AC.

Iniciativa: `docs/source/gestion/pm/api/iniciativas/implementar-load-tests-performance`.

## SLO (de `slos.py`, anclados a RNF-PERF)

| Grupo | Endpoints | P95 | RNF |
|---|---|---|---|
| `read_simple` | catálogo, detalle, ver carrito | ≤ 400 ms | RNF-PERF-001 |
| `search` | búsqueda con filtros | ≤ 600 ms | RNF-PERF-001 |
| `write` | add-to-cart, checkout, crear orden | ≤ 500 ms | RNF-PERF-002 |
| `pagination` | listados grandes / reportes | ≤ 1200 ms | RNF-PERF-003 |

## Cómo correr (WSL / CI — NO el contenedor del agente, L-010)

```bash
pip install locust            # o: uv pip install locust
# Con la api levantada en http://localhost:8000 (PostgreSQL + seed QA):
locust -f load_tests/locustfile.py --host http://localhost:8000 \
       --headless -u 50 -r 5 -t 2m
```

Al terminar, el hook `check_slo` imprime `[SLO PASS|FAIL]` por endpoint
(P95 observado vs SLO) y fija el exit code (0 = todo dentro de SLO) →
apto para gate de CI.

Solo un grupo:

```bash
locust -f load_tests/locustfile.py --tags read_simple --headless \
       --host http://localhost:8000 -u 50 -r 5 -t 1m
```

## Pendiente antes de CI (TODO del esqueleto)

1. **Auth:** `on_start` debe loguear (`POST /api/v1/auth/login/`) y fijar
   el `Authorization: Bearer <JWT>`; el flujo anónimo de carrito usa el
   `X-Cart-Token` devuelto.
2. **Datos de seed:** parametrizar `product_id`/slug/categoría contra el
   seed real de QA (`manage.py create_seed_catalog`), no valores demo.
3. **Payloads reales:** `checkout` requiere carrito poblado +
   `Idempotency-Key`.
4. **Concurrencia:** los AC-07 también exigen consistencia bajo carga;
   añadir aserciones de integridad (p. ej. stock no negativo) tras el run.
5. **CI:** target `make load-ci` (o job) que levante api+PostgreSQL, corra
   en `--headless` y falle si `check_slo` da exit 1.

## Por qué esto cierra los 153 AC-07

Cada AC-07 ("P95 < Xms", "operaciones concurrentes mantienen
consistencia") es una instancia del mismo NFR de performance. La suite
valida ese NFR **una vez por grupo de endpoint**; los marcadores
`:test:` de los UC referencian la validación NFR (`NFR-PERF transversal`),
no un test por-UC. Ver `definition-of-done.rst` (regla pareja de NFR).
