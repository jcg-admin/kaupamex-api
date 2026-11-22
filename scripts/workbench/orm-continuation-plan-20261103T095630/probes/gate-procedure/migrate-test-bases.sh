#!/usr/bin/env bash
# Aplica las migraciones pendientes a las cinco bases de prueba, en serie
# (nunca dos reconstrucciones de la misma base a la vez), y publica cuántas
# quedan sin aplicar en cada una.
# Uso: bash migrate-test-bases.sh [app]   (sin app: todas)
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
export PATH="$PWD/.venv/bin:$PATH" DJANGO_SETTINGS_MODULE=config.settings.testing
for db in orm_x2hokp_qa orm_x2hokp_qa_gw0 orm_x2hokp_qa_gw1 orm_x2hokp_qa_gw2 orm_x2hokp_qa_gw3; do
    DB_QA_NAME="$db" python src/manage.py migrate ${1:-} --noinput >/dev/null
    pending=$(DB_QA_NAME="$db" python src/manage.py showmigrations ${1:-} --plan | grep -c '^\[ \]' || true)
    echo "$db $pending"
done
python src/manage.py makemigrations --check --dry-run >/dev/null && echo "No changes detected"
echo DONE
