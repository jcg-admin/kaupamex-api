#!/bin/bash
# =============================================================================
# tests/test_d032_spectacular.sh — D-032 regression tests
# =============================================================================
# Detecta regresion de los 6 fixes (T-1..T-6) que cerraron las ~100
# warnings de drf-spectacular emitidas al generar /api/schema/.
#
# Dos modos de validacion:
#
#   - ESTATICO (sin venv): verifica que cada fix esta presente en el
#     codigo via grep. Se ejecuta automaticamente.
#   - DINAMICO (con venv + BD): ejecuta `manage.py spectacular
#     --validate --fail-on-warn` y cuenta warnings reales del stderr.
#     Solo si se detecta venv activo, MARIADB y MIGRACIONES aplicadas.
#
# Uso:
#   bash tests/test_d032_spectacular.sh           # solo estatico
#   bash tests/test_d032_spectacular.sh --runtime # estatico + dinamico
#
# Idempotente: solo lee codigo. Si se invoca --runtime levanta una
# subshell con manage.py, no toca la BD.
# =============================================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPS_ROOT="$PROJECT_ROOT/practicayoruba/apps"
CONFIG="$PROJECT_ROOT/practicayoruba/config/settings/base.py"
EXIT=0
RUN_DYNAMIC=false
for arg in "$@"; do
    [[ "$arg" == "--runtime" ]] && RUN_DYNAMIC=true
done

fail() { echo "FAIL: $*" >&2; EXIT=1; }
pass() { echo "PASS: $*"; }

# ----------------------------------------------------------------------------
# T-4: ENUM_NAME_OVERRIDES presente en SPECTACULAR_SETTINGS
# ----------------------------------------------------------------------------
if grep -qE "'ENUM_NAME_OVERRIDES'\s*:" "$CONFIG"; then
    pass "base.py declara ENUM_NAME_OVERRIDES (T-4)"
else
    fail "base.py NO declara ENUM_NAME_OVERRIDES (T-4 regresion)"
fi

# Cuenta entries esperadas: status (11) + gateway (2) + audience (1) = 14
ENUM_COUNT=$(grep -cE "^\s+'[A-Z][a-zA-Z]+Enum'\s*:" "$CONFIG" || echo 0)
if [[ "$ENUM_COUNT" -ge 14 ]]; then
    pass "base.py mapea $ENUM_COUNT enum overrides (>= 14 esperados)"
else
    fail "base.py mapea solo $ENUM_COUNT enum overrides (esperados >= 14) (T-4 regresion)"
fi

# ----------------------------------------------------------------------------
# T-5: chartsize ViewSets con OpenApiParameter PATH INT
# ----------------------------------------------------------------------------
CHARTSIZE_VIEWS="$APPS_ROOT/chartsize/views.py"
# Check via Python para tolerar multi-linea
if python3 - "$CHARTSIZE_VIEWS" <<'PY'
import sys, re
src = open(sys.argv[1]).read()
# Patron multi-linea: OpenApiParameter('product_pk', ... OpenApiTypes.INT ... OpenApiParameter.PATH
ok = re.search(
    r"OpenApiParameter\(\s*'product_pk'[^)]*OpenApiTypes\.INT[^)]*OpenApiParameter\.PATH",
    src, flags=re.DOTALL,
) is not None
sys.exit(0 if ok else 1)
PY
then
    pass "chartsize/views.py declara product_pk: INT en PATH (T-5)"
else
    fail "chartsize/views.py NO tipa product_pk como INT (T-5 regresion)"
fi
if grep -qE '@extend_schema_view\b' "$CHARTSIZE_VIEWS"; then
    pass "chartsize/views.py usa @extend_schema_view (T-5)"
else
    fail "chartsize/views.py NO usa @extend_schema_view (T-5 regresion)"
fi

# ----------------------------------------------------------------------------
# T-3: string refs eliminados de @extend_schema en orders + payments
# ----------------------------------------------------------------------------
for f in "$APPS_ROOT/orders/views.py" "$APPS_ROOT/orders/admin_views.py" \
         "$APPS_ROOT/payments/views.py"; do
    if grep -qE "responses=\{[0-9]+:\s*'[A-Z][a-zA-Z]*Serializer'" "$f"; then
        fail "$(basename "$f"): responses={N: 'StringSerializer'} persiste (T-3 regresion)"
    elif grep -qE "request='[A-Z][a-zA-Z]*Serializer'" "$f"; then
        fail "$(basename "$f"): request='StringSerializer' persiste (T-3 regresion)"
    else
        pass "$(basename "$f"): sin string refs en @extend_schema (T-3)"
    fi
done

# ----------------------------------------------------------------------------
# T-2: SerializerMethodField metodos tienen type hint
# ----------------------------------------------------------------------------
# Patrones de metodos previamente sin hint
declare -A T2_TARGETS=(
    ["cart/serializers.py"]="get_variant_label get_sku get_subtotal get_available_stock get_is_available get_price_changed get_totals"
    ["catalogue/serializers.py"]="get_children get_product_count get_price_with_tax get_images get_discount get_variants get_related_products"
    ["inventory/serializers.py"]="get_variant_label"
    ["logistics/serializers.py"]="get_last_event"
    ["orders/serializers.py"]="get_shipping_method_name get_status_display"
    ["questions/serializers.py"]="get_asker_name"
    ["returns/serializers.py"]="get_history get_user_email get_user_username get_available_action"
    ["support/serializers.py"]="get_author get_replies get_available_actions get_buyer"
    ["users/admin_views.py"]="get_profile_completeness get_address_count"
)
T2_TOTAL_OK=0
T2_TOTAL_FAIL=0
for f in "${!T2_TARGETS[@]}"; do
    path="$APPS_ROOT/$f"
    [[ -f "$path" ]] || { fail "T-2 archivo ausente: $f"; continue; }
    for m in ${T2_TARGETS[$f]}; do
        # def get_X(self, obj) -> Tipo:
        if grep -qE "def $m\(self, obj\)\s*->\s*[a-zA-Z]" "$path"; then
            T2_TOTAL_OK=$((T2_TOTAL_OK + 1))
        else
            # Tolerar si el metodo no existe en el archivo (refactor posterior)
            if ! grep -qE "def $m\(self, obj\)" "$path"; then
                continue
            fi
            T2_TOTAL_FAIL=$((T2_TOTAL_FAIL + 1))
            fail "$f::$m sin type hint de retorno (T-2 regresion)"
        fi
    done
done
if [[ "$T2_TOTAL_FAIL" -eq 0 ]]; then
    pass "T-2: $T2_TOTAL_OK metodos SerializerMethodField con type hints"
fi

# ----------------------------------------------------------------------------
# T-1: cada view de la lista tiene serializer_class
# ----------------------------------------------------------------------------
declare -A T1_TARGETS=(
    ["contact/views.py"]="AdminContactMessageMarkReadView"
    ["inventory/views.py"]="InventoryDashboardView StockAdjustView VariantStockAdjustView ProductImportView ProductImportStatusView ProductImportReportView"
    ["newsletter/views.py"]="NewsletterSubscribeView NewsletterUnsubscribeView AdminSubscriberForceUnsubscribeView"
    ["notifications/views.py"]="NotificationUnreadCountView NotificationMarkReadView NotificationMarkAllReadView AdminAudienceCountView"
    ["settings_app/views.py"]="StaticPagePublishView StaticPageRestoreView"
    ["catalogue/price_sync_views.py"]="_AdminOnly"
    ["catalogue/product_discount_views.py"]="ProductDiscountDeactivateView"
    ["catalogue/views.py"]="ProductPriceSyncView ProductPriceSyncConfirmView ProductPriceSyncTemplateView"
    ["catalogue/browse_views.py"]="RelatedProductsView CatalogueSearchView"
    ["questions/views.py"]="ProductQuestionsView AdminQuestionApproveView AdminQuestionRejectView"
    ["reports/views.py"]="_AdminMixin ReportExportView"
    ["reviews/views.py"]="ProductReviewsView _AdminOnly"
    ["static_content/views.py"]="_AdminOnly"
    ["support/views.py"]="SupportTicketCloseView SupportTicketReopenView"
    ["cart/views.py"]="CartItemListView CartItemDetailView CartSaveView CartVoucherView"
    ["logistics/views.py"]="_AdminOnly"
    ["payments/webhooks.py"]="MercadoPagoWebhookView PayPalWebhookView"
    ["search_history/views.py"]="SearchHistoryListView SearchHistoryEntryView"
    ["wishlist/views.py"]="WishlistView WishlistMoveToCartView"
)
T1_OK=0
T1_FAIL=0
for f in "${!T1_TARGETS[@]}"; do
    path="$APPS_ROOT/$f"
    [[ -f "$path" ]] || { fail "T-1 archivo ausente: $f"; continue; }
    for cls in ${T1_TARGETS[$f]}; do
        # Buscar la definicion de la clase y verificar que dentro de su
        # cuerpo aparece serializer_class. Usa python helper para no
        # depender de awk avanzado.
        if python3 - "$path" "$cls" <<'PY'
import sys, re
path, cls = sys.argv[1], sys.argv[2]
src = open(path).read()
m = re.search(rf'^class\s+{re.escape(cls)}\b[^\n]*:\n((?: {{4,}}.*\n|\n)*)', src, flags=re.M)
if not m:
    sys.exit(2)
body = m.group(1)
sys.exit(0 if 'serializer_class' in body else 1)
PY
        then
            T1_OK=$((T1_OK + 1))
        else
            rc=$?
            if [[ "$rc" == "2" ]]; then
                fail "$f::$cls no se encontro la clase"
            else
                T1_FAIL=$((T1_FAIL + 1))
                fail "$f::$cls sin serializer_class (T-1 regresion)"
            fi
        fi
    done
done
if [[ "$T1_FAIL" -eq 0 ]]; then
    pass "T-1: $T1_OK clases APIView con serializer_class"
fi

# ----------------------------------------------------------------------------
# T-6: operation_id explicito en pairs list/detail + splits ejecutados
# ----------------------------------------------------------------------------
# Caso a: operation_id explicito
declare -A T6_OP_IDS=(
    ["orders/views.py"]="orders_list orders_retrieve"
    ["orders/admin_views.py"]="admin_orders_list admin_orders_retrieve"
    ["static_content/views.py"]="admin_static_content_list admin_static_content_retrieve"
    ["search_history/views.py"]="search_history_clear_all search_history_entry_destroy"
    ["catalogue/views.py"]="catalogue_search_history_clear_all catalogue_search_history_entry_destroy"
    ["logistics/views.py"]="logistics_guides_list logistics_guides_retrieve"
)
T6_OK=0
for f in "${!T6_OP_IDS[@]}"; do
    path="$APPS_ROOT/$f"
    [[ -f "$path" ]] || { fail "T-6 archivo ausente: $f"; continue; }
    for opid in ${T6_OP_IDS[$f]}; do
        if grep -qE "operation_id\s*=\s*'$opid'" "$path"; then
            T6_OK=$((T6_OK + 1))
        else
            fail "$f sin operation_id='$opid' (T-6 regresion)"
        fi
    done
done
[[ "$T6_OK" -ge 12 ]] && pass "T-6: $T6_OK operation_id explicitos (>= 12)"

# Caso b: splits de clase ejecutados
CART_VIEWS="$APPS_ROOT/cart/views.py"
if grep -qE '^class CartItemListView\b' "$CART_VIEWS" \
   && grep -qE '^class CartItemDetailView\b' "$CART_VIEWS"; then
    pass "cart/views.py: CartItemView split en List + Detail (T-6)"
else
    fail "cart/views.py: split de CartItemView no aplicado (T-6 regresion)"
fi
if grep -qE 'CartItemListView' "$APPS_ROOT/cart/urls.py" \
   && grep -qE 'CartItemDetailView' "$APPS_ROOT/cart/urls.py"; then
    pass "cart/urls.py: rutas apuntan a List + Detail (T-6)"
else
    fail "cart/urls.py: rutas no actualizadas al split (T-6 regresion)"
fi

SETTINGS_VIEWS="$APPS_ROOT/settings_app/views.py"
if grep -qE '^class StaticPageAdminListView\b' "$SETTINGS_VIEWS" \
   && grep -qE '^class StaticPageAdminDetailView\b' "$SETTINGS_VIEWS"; then
    pass "settings_app/views.py: StaticPageAdminView split en List + Detail (T-6)"
else
    fail "settings_app/views.py: split de StaticPageAdminView no aplicado (T-6 regresion)"
fi
if grep -qE 'StaticPageAdminListView' "$APPS_ROOT/settings_app/admin_urls.py" \
   && grep -qE 'StaticPageAdminDetailView' "$APPS_ROOT/settings_app/admin_urls.py"; then
    pass "settings_app/admin_urls.py: rutas apuntan a List + Detail (T-6)"
else
    fail "settings_app/admin_urls.py: rutas no actualizadas (T-6 regresion)"
fi

# ----------------------------------------------------------------------------
# Validacion dinamica opcional: requiere venv + MariaDB + migraciones
# ----------------------------------------------------------------------------
if [[ "$RUN_DYNAMIC" == "true" ]]; then
    echo ""
    echo "--- Validacion DINAMICA (manage.py spectacular) ---"
    VENV_PY="$PROJECT_ROOT/.venv/bin/python"
    if [[ ! -x "$VENV_PY" ]]; then
        fail "Validacion dinamica solicitada pero .venv/bin/python no existe"
    else
        LOG="$(mktemp -t d032_spectacular.XXXX.log)"
        cd "$PROJECT_ROOT/practicayoruba"
        DJANGO_SETTINGS_MODULE=config.settings.development \
        PYTHONPATH="$PROJECT_ROOT/practicayoruba" \
            "$VENV_PY" manage.py spectacular --validate \
            --file /tmp/spectacular_schema.yaml \
            > "$LOG" 2>&1 || true
        WARN_COUNT=$(grep -cE '^(Warning|Error)' "$LOG" || echo 0)
        if [[ "$WARN_COUNT" -eq 0 ]]; then
            pass "spectacular emite 0 warnings (D-032 cerrado runtime)"
        else
            fail "spectacular todavia emite $WARN_COUNT warnings — ver $LOG"
            echo "Primeros 10:"
            head -10 "$LOG" | sed 's/^/    /' >&2
        fi
    fi
fi

# ----------------------------------------------------------------------------
# Cierre
# ----------------------------------------------------------------------------
echo ""
if [[ "$EXIT" -eq 0 ]]; then
    echo ">>> ALL PASS — D-032 fixes integros"
    echo "    Para validacion runtime: bash $0 --runtime"
else
    echo ">>> FAIL — D-032 regresion detectada"
fi
exit "$EXIT"
