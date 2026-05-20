# Makefile — api targets de mantenimiento / CI.
#
# Targets para ejecucion local y en pipelines de CI futuros.
# Mantiene paridad con ui/package.json scripts equivalentes.
.PHONY: help check-lazy check-lazy-ci check-canon check-canon-ci test test-coverage install-hooks

help:
	@echo 'Targets:'
	@echo '  make check-lazy        Audit AST: 0 lazy imports en apps/** y tests/**'
	@echo '  make check-lazy-ci     Idem, exit code != 0 si hay violaciones'
	@echo '  make check-canon       Canon-idioma: 0 identifiers ES en apps/** (soft)'
	@echo '  make check-canon-ci    Idem, exit code != 0 si hay violaciones'
	@echo '  make test              Pytest suite completa'
	@echo '  make test-coverage     Pytest con coverage'
	@echo '  make install-hooks     Activar .githooks/ via core.hooksPath'

# Audit local — imprime hallazgos pero no falla (para inspeccion manual).
check-lazy:
	python3 scripts/check_no_lazy_imports.py || true

# Audit estricto — para CI. Exit != 0 dispara fallo en pipeline.
check-lazy-ci:
	python3 scripts/check_no_lazy_imports.py

# Canon-idioma soft — imprime hallazgos pero retorna exit 0.
check-canon:
	python3 ../docs/scripts/check_canon_idioma.py --repo-root .. --soft

# Canon-idioma estricto — exit != 0 si hay literales ES fuera del allowlist.
check-canon-ci:
	python3 ../docs/scripts/check_canon_idioma.py --repo-root ..

test:
	pytest

test-coverage:
	pytest --cov=practicayoruba --cov-report=term-missing

install-hooks:
	bash scripts/install-hooks.sh
