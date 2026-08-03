# Makefile — api targets de mantenimiento / CI.
#
# Targets para ejecucion local y en pipelines de CI futuros.
# Mantiene paridad con ui/package.json scripts equivalentes.
.PHONY: help check-names check-names-ci check-layout check-layout-ci check-lazy check-lazy-ci check-cycles check-cycles-ci check-catalog check-catalog-ci check-canon check-canon-ci test test-coverage install-hooks db-up ci-test ci-test-fast

help:
	@echo 'Targets:'
	@echo '  make check-names       Nombre de addon contra odoo-tools (H-API-119)'
	@echo '  make check-names-ci    Idem, exit != 0 tambien con deuda heredada'
	@echo '  make check-layout      Capas estructurales en paquete (H-API-238)'
	@echo '  make check-layout-ci   Idem, exit != 0 tambien con deuda heredada'
	@echo '  make check-lazy        Audit AST: 0 lazy imports en apps/** y tests/**'
	@echo '  make check-lazy-ci     Idem, exit code != 0 si hay violaciones'
	@echo '  make check-catalog     Coherencia de los authz_catalog.py (SOL-100)'
	@echo '  make check-catalog-ci  Idem, exit code != 0 si hay incoherencias'
	@echo '  make check-cycles      Direccion de dependencias: 0 inversiones nuevas'
	@echo '  make check-cycles-ci   Idem, exit code != 0 si hay inversiones nuevas'
	@echo '  make check-canon       Canon-idioma: 0 identifiers ES en apps/** (soft)'
	@echo '  make check-canon-ci    Idem, exit code != 0 si hay violaciones'
	@echo '  make test              Pytest suite completa'
	@echo '  make test-coverage     Pytest con coverage'
	@echo '  make install-hooks     Activar .githooks/ via core.hooksPath'
	@echo '  make db-up             Arranca MariaDB via el script de db (socket)'
	@echo '  make ci-test           db-up + pytest suite completa (--reuse-db)'
	@echo '  make ci-test-fast      db-up + subset de humo cart/ (--reuse-db)'

# Audit local — imprime hallazgos pero no falla (para inspeccion manual).
check-names:
	python3 scripts/check_addon_names.py

check-names-ci:
	python3 scripts/check_addon_names.py --strict

check-layout:
	python3 scripts/check_addon_layout.py

check-layout-ci:
	python3 scripts/check_addon_layout.py --strict

check-lazy:
	python3 scripts/check_no_lazy_imports.py || true

# Audit estricto — para CI. Exit != 0 dispara fallo en pipeline.
check-lazy-ci:
	python3 scripts/check_no_lazy_imports.py

# Silencios de excepción justificados (AC uc-sys-06) — soft / CI.
check-silent:
	python3 scripts/check_silent_oks.py || true

check-silent-ci:
	python3 scripts/check_silent_oks.py

# Canon-idioma soft — imprime hallazgos pero retorna exit 0.
check-cycles:
	@python3 scripts/check_addon_cycles.py --report

check-cycles-ci:
	@python3 scripts/check_addon_cycles.py

# Declaracion del catalogo L0 (SOL-100) — coherencia estatica de los
# authz_catalog.py: addon instalado, sin duenos duplicados, sin capacidades
# huerfanas, sin aristas depends colgantes.
check-catalog:
	@python3 scripts/check_catalog_declaration.py --report

check-catalog-ci:
	@python3 scripts/check_catalog_declaration.py

check-canon:
	python3 $$(ls -d ../kaupamex-docs ../docs 2>/dev/null | head -1)/scripts/check_canon_idioma.py --repo-root .. --soft

# Canon-idioma estricto — exit != 0 si hay literales ES fuera del allowlist.
check-canon-ci:
	python3 $$(ls -d ../kaupamex-docs ../docs 2>/dev/null | head -1)/scripts/check_canon_idioma.py --repo-root ..

test:
	pytest

test-coverage:
	pytest --cov=src --cov-report=term-missing

install-hooks:
	bash scripts/install-hooks.sh

# --- Coordinacion CI/CD: db + api ---------------------------------------

# Arranca MariaDB (idempotente) via el script del submodulo db.
# DB_DIR permite override; fallback a ../db y luego a la ruta absoluta
# conocida del contenedor.
db-up:
	@DB_DIR="$${DB_DIR:-../db}"; \
	if [ ! -d "$$DB_DIR" ]; then DB_DIR=/home/user/kaupamex-db; fi; \
	echo "db-up: usando DB_DIR=$$DB_DIR"; \
	bash "$$DB_DIR/scripts/start_db.sh"

# Suite completa contra MariaDB real (--reuse-db: no recrea schema).
ci-test: db-up
	uv run pytest --reuse-db -q

# Subset rapido de humo (cart/) — smoke test de CI.
ci-test-fast: db-up
	uv run pytest tests/integration/cart/ -q --reuse-db
