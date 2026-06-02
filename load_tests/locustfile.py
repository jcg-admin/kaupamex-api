"""
locustfile.py — esqueleto de la suite de load tests (RNF-PERF).

Cierra los 153 AC-07 (performance/concurrencia) a nivel de NFR: mide el
P95 por grupo de endpoint y lo compara contra el SLO de ``slos.py``. NO
se valida AC por AC — la performance es un NFR transversal.

Cómo correr (en WSL/CI, contra una api levantada — NO en el contenedor
del agente, L-010):

    pip install locust            # o: uv pip install locust
    # api corriendo en http://localhost:8000
    locust -f load_tests/locustfile.py --host http://localhost:8000 \
           --headless -u 50 -r 5 -t 2m            # 50 usuarios, 2 min

    # Solo un grupo (tags):
    locust -f load_tests/locustfile.py --tags read_simple --headless ...

Al finalizar, ``check_slo`` (hook ``test_stop``) imprime PASS/FAIL por
grupo comparando el P95 observado vs ``SLO_P95_MS`` y fija el exit code
(0 = todos los grupos dentro de SLO).

Estado: **esqueleto**. Los TODO marcan dónde inyectar auth (JWT),
payloads reales y datos de seed antes de correrlo en CI.
"""
from __future__ import annotations

import os

from locust import HttpUser, between, events, tag, task

from slos import SLO_P95_MS, SLO_SOURCE

# Producto/categoría de seed para los GET de detalle (TODO: parametrizar
# contra el seed real de QA — ver db/seed_catalogo.sql).
SEED_PRODUCT_SLUG = os.getenv("LOADTEST_PRODUCT_SLUG", "producto-demo")
SEED_CATEGORY = os.getenv("LOADTEST_CATEGORY", "ategun")


class CatalogReadUser(HttpUser):
    """Lectura de catálogo (RNF-PERF-001) — el grueso del tráfico."""

    wait_time = between(1, 3)

    @tag("read_simple")
    @task(5)
    def list_catalogue(self):
        self.client.get("/api/v1/catalogue/", name="GET /catalogue [read_simple]")

    @tag("read_simple")
    @task(3)
    def product_detail(self):
        self.client.get(
            f"/api/v1/products/{SEED_PRODUCT_SLUG}/",
            name="GET /products/:slug [read_simple]",
        )

    @tag("search")
    @task(2)
    def search_with_filters(self):
        self.client.get(
            f"/api/v1/search/?q=collar&category={SEED_CATEGORY}",
            name="GET /search [search]",
        )

    @tag("pagination")
    @task(1)
    def deep_pagination(self):
        self.client.get(
            "/api/v1/catalogue/?page=5&page_size=24",
            name="GET /catalogue?page=N [pagination]",
        )


class CheckoutWriteUser(HttpUser):
    """Escritura crítica de compra (RNF-PERF-002)."""

    wait_time = between(2, 5)

    def on_start(self):
        # TODO: autenticar (POST /api/v1/auth/login/) y guardar el JWT en
        # self.client.headers["Authorization"] = f"Bearer {token}".
        # Para el flujo anónimo de carrito basta el X-Cart-Token devuelto.
        self.cart_token = None

    @tag("write")
    @task(3)
    def add_to_cart(self):
        # TODO: usar product_id real del seed; capturar X-Cart-Token.
        self.client.post(
            "/api/v1/cart/items/",
            json={"product_id": 1, "quantity": 1},
            name="POST /cart/items [write]",
        )

    @tag("write")
    @task(1)
    def checkout(self):
        # TODO: requiere carrito poblado + JWT + Idempotency-Key.
        self.client.post(
            "/api/v1/checkout/",
            json={},
            name="POST /checkout [write]",
        )


# ─── Validación de SLO al cierre ─────────────────────────────────────────────
@events.test_stop.add_listener
def check_slo(environment, **_kw):
    """Compara el P95 observado por grupo (tag en el name) vs el SLO."""
    failures = []
    stats = environment.stats
    # Agrupa por el tag entre corchetes en el name: "... [grupo]".
    for entry in stats.entries.values():
        name = entry.name
        if "[" not in name or "]" not in name:
            continue
        group = name[name.rfind("[") + 1:name.rfind("]")]
        slo = SLO_P95_MS.get(group)
        if slo is None or entry.num_requests == 0:
            continue
        p95 = entry.get_response_time_percentile(0.95)
        status = "PASS" if p95 <= slo else "FAIL"
        if status == "FAIL":
            failures.append((name, group, p95, slo))
        print(f"[SLO {status}] {name}: P95={p95}ms <= {slo}ms "
              f"({SLO_SOURCE.get(group, '?')})")
    if failures:
        print(f"\nSLO FAIL: {len(failures)} endpoint(s) exceden su P95.")
        environment.process_exit_code = 1
    else:
        print("\nSLO OK: todos los grupos dentro de su P95.")
        environment.process_exit_code = 0
