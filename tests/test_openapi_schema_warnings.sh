#!/bin/bash
# =============================================================================
# tests/test_openapi_schema_warnings.sh
# =============================================================================
# Asegura que la generacion del schema OpenAPI por drf-spectacular emita
# CERO errores y CERO warnings.
#
# Gate autoritativo: `manage.py spectacular --validate`. Cualquier error o
# warning de validacion (campo sin tipo, colision de enum/operationId,
# schema OpenAPI invalido) hace fallar el comando y este test.
#
# Historia: la version previa de este script validaba via grep heuristico
# (esperaba literales `serializer_class=` / `operation_id=` / type hints
# `-> Tipo:` en los metodos). Esa heuristica dejo de coincidir con la
# estrategia real de anotacion del proyecto (@extend_schema /
# @extend_schema_field / @extend_schema_view sobre vistas APIView), y
# producia decenas de falsos positivos mientras el schema real validaba
# limpio. Se reemplazo por el unico gate confiable: la generacion real del
# schema con --validate. Ver backlog OpenAPI hardening (warnings 64->0).
#
# Uso:
#   bash tests/test_openapi_schema_warnings.sh
#
# Requiere: uv + MariaDB activa (socket) + migraciones aplicadas en QA.
# Idempotente: solo genera el schema en /tmp, no toca la BD.
# =============================================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCHEMA_OUT="$(mktemp -t openapi_schema.XXXX.yml)"
LOG="$(mktemp -t openapi_validate.XXXX.log)"

echo "--- Gate autoritativo: spectacular --validate (0 errores + 0 warnings) ---"

# --skip-checks evita el system check payments.E001 (MERCADOPAGO gateway),
# drift de entorno conocido (H-INV-RESTOCK-01) ortogonal al schema.
cd "$PROJECT_ROOT/practicayoruba"
if uv run python manage.py spectacular --validate --skip-checks \
        --file "$SCHEMA_OUT" > "$LOG" 2>&1; then
    SPEC_RC=0
else
    SPEC_RC=$?
fi

# spectacular solo imprime el bloque "Schema generation summary" cuando hay
# warnings o errores; en un schema limpio la salida es vacia. Contamos
# cualquier linea de Warning/Error como fallo.
WARN_ERR_COUNT=$(grep -cE '(^|\s)(Warning|Error)' "$LOG" || true)

if [[ "$SPEC_RC" -eq 0 && "$WARN_ERR_COUNT" -eq 0 ]]; then
    echo "PASS: spectacular --validate emite 0 errores y 0 warnings"
    echo ">>> ALL PASS — schema OpenAPI limpio"
    rm -f "$SCHEMA_OUT" "$LOG"
    exit 0
fi

echo "FAIL: spectacular --validate reporto problemas (rc=$SPEC_RC, lineas Warning/Error=$WARN_ERR_COUNT)" >&2
echo "--- salida del comando ---" >&2
cat "$LOG" >&2
rm -f "$SCHEMA_OUT"
echo ">>> FAIL — el schema OpenAPI tiene errores o warnings (log: $LOG)" >&2
exit 1
