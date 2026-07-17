"""
Serializers — addons.returns.

Cumplen los contratos JSON declarados en UC-RET-01..06 (PARTE 7C).
"""
from decimal import Decimal
from rest_framework import serializers
from addons.authz.services import is_superadmin
from .models import (
    ReturnEvidence,
    ReturnHistoryEntry,
    ReturnItem,
    ReturnRequest,
)

# UC-RET-01 AC-06: limites de evidencia fotografica.
EVIDENCE_MAX_FILES = 5
EVIDENCE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB por archivo.
EVIDENCE_ALLOWED_CONTENT_TYPES = {'image/jpeg', 'image/png'}



# ────────────────────────────── Items ──────────────────────────────────────────
class ReturnItemSerializer(serializers.ModelSerializer):
    """Representacion ligera de un ReturnItem."""

    class Meta:
        model = ReturnItem
        fields = ['id', 'product_id', 'quantity', 'product_condition']
        read_only_fields = fields


class ReturnItemInputSerializer(serializers.Serializer):
    """Item entrante al crear una solicitud."""

    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, required=False, default=1)


# ────────────────────────────── Historial ────────────────────────────────────
class ReturnHistoryEntrySerializer(serializers.ModelSerializer):
    """Historial de cambios de estado expuesto por UC-RET-04."""

    actor = serializers.SerializerMethodField()

    class Meta:
        model = ReturnHistoryEntry
        fields = ['id', 'status_to', 'actor', 'justification', 'created_at']
        read_only_fields = fields

    def get_actor(self, obj):
        if obj.actor is None:
            return 'SYSTEM'
        return 'ADMIN' if is_superadmin(obj.actor) else 'BUYER'


# ────────────────────────────── Evidencia (UC-RET-01 AC-06) ──────────────────
class ReturnEvidenceSerializer(serializers.ModelSerializer):
    """Evidencia fotografica asociada a una devolucion (solo lectura)."""

    class Meta:
        model = ReturnEvidence
        fields = ['id', 'image', 'created_at']
        read_only_fields = fields


# ────────────────────────────── UC-RET-01 (create) ───────────────────────────
class ReturnCreateSerializer(serializers.Serializer):
    """UC-RET-01 — request body.

    Acepta ``order_number`` (el identificador visible al comprador, p.ej.
    'PY-AB12CD34') en lugar del PK interno. El lookup por order_number
    ocurre en la view; el serializer solo valida formato.
    """

    order_number = serializers.CharField(min_length=1, max_length=20)
    reason = serializers.ChoiceField(choices=ReturnRequest.Reason.choices)
    description = serializers.CharField(min_length=20, max_length=10000)
    items = ReturnItemInputSerializer(many=True, required=False, allow_empty=False)
    # UC-RET-01 AC-06: hasta 5 imagenes (JPEG/PNG, <=5MB) via multipart.
    # La clave es ``photos`` para alinear con el contrato que ya emite la
    # UI (``ReturnCreatePage`` / ``returnsSlice.createReturnRequest`` arma
    # un ``FormData`` con ``form.append('photos', file)``). Se persisten en
    # la relacion ``ReturnRequest.evidence`` (ver el modelo y el detalle).
    photos = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        write_only=True,
        max_length=EVIDENCE_MAX_FILES,
        help_text='Hasta 5 imagenes (image/jpeg|png, <=5MB cada una).',
    )

    def validate_photos(self, files):
        for f in files:
            if getattr(f, 'size', 0) > EVIDENCE_MAX_BYTES:
                raise serializers.ValidationError(
                    f'Cada archivo debe pesar <= 5MB (recibido {f.size} bytes).'
                )
            content_type = getattr(f, 'content_type', None)
            if content_type and content_type not in EVIDENCE_ALLOWED_CONTENT_TYPES:
                raise serializers.ValidationError(
                    f'Tipo no permitido ({content_type}); solo image/jpeg o '
                    f'image/png.'
                )
        return files


# ────────────────────────────── UC-RET-04 (buyer list/detail) ────────────────────────
class ReturnListSerializer(serializers.ModelSerializer):
    """UC-RET-04 — listado de devoluciones del comprador."""

    class Meta:
        model = ReturnRequest
        fields = [
            'id', 'order_id', 'reason', 'status',
            'refund_amount', 'refund_at', 'received_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class ReturnDetailSerializer(serializers.ModelSerializer):
    """UC-RET-04 — detalle con bloque ``history`` e items."""

    items = ReturnItemSerializer(many=True, read_only=True)
    history = serializers.SerializerMethodField()
    evidence = ReturnEvidenceSerializer(many=True, read_only=True)

    class Meta:
        model = ReturnRequest
        fields = [
            'id', 'order_id', 'reason', 'description', 'status',
            'refund_amount', 'refund_at', 'received_at',
            'rejection_reason', 'created_at', 'updated_at',
            'items', 'history', 'evidence',
        ]
        read_only_fields = fields

    def get_history(self, obj) -> list:
        # UC-RET-04 PARTE 3 paso 3 (DEC-RET-07): ordenar DESC para que el
        # comprador vea el ultimo evento del lifecycle arriba.
        qs = obj.history_entries.all().order_by('-created_at')
        return ReturnHistoryEntrySerializer(qs, many=True).data


# ────────────────────────────── UC-RET-05 (admin queue) ───────────────────────────
class AdminReturnListSerializer(serializers.ModelSerializer):
    """UC-RET-05 — fila de la bandeja admin con datos del comprador."""

    user_id = serializers.IntegerField(read_only=True)
    user_email = serializers.SerializerMethodField()
    user_username = serializers.SerializerMethodField()
    available_action = serializers.SerializerMethodField()

    class Meta:
        model = ReturnRequest
        fields = [
            'id', 'user_id', 'user_email', 'user_username',
            'order_id', 'reason', 'status',
            'refund_amount', 'refund_at', 'received_at',
            'created_at', 'updated_at', 'available_action',
        ]
        read_only_fields = fields

    def get_user_email(self, obj) -> str | None:
        return getattr(obj.user, 'email', None)

    def get_user_username(self, obj) -> str | None:
        # Party (T-201): username == email (compat de contrato hasta B3-ui).
        return getattr(obj.user, 'email', None)

    def get_available_action(self, obj) -> str | None:
        """UC-RET-05 PARTE 8.4: accion segun estado."""
        if obj.status == ReturnRequest.Status.PENDING_REVIEW:
            return 'REVIEW'
        if obj.status == ReturnRequest.Status.INFO_REQUESTED:
            return 'FOLLOW_UP'
        if obj.status == ReturnRequest.Status.APPROVED:
            if obj.received_at is None:
                return 'REGISTER_RECEPTION'
            return 'PROCESS_REFUND'
        if obj.status == ReturnRequest.Status.RECEIVED:
            return 'PROCESS_REFUND'
        return None


class AdminReturnDetailSerializer(ReturnDetailSerializer):
    """Detalle admin: incluye datos del comprador adicionales."""

    user_id = serializers.IntegerField(read_only=True)
    user_email = serializers.SerializerMethodField()
    user_username = serializers.SerializerMethodField()

    class Meta(ReturnDetailSerializer.Meta):
        fields = ReturnDetailSerializer.Meta.fields + [
            'user_id', 'user_email', 'user_username',
        ]
        read_only_fields = fields

    def get_user_email(self, obj) -> str | None:
        return getattr(obj.user, 'email', None)

    def get_user_username(self, obj) -> str | None:
        # Party (T-201): username == email (compat de contrato hasta B3-ui).
        return getattr(obj.user, 'email', None)


# ────────────────────────────── UC-RET-02 (admin decisions) ──────────────────────────
class ReturnApproveSerializer(serializers.Serializer):
    """UC-RET-02 approve."""

    justification = serializers.CharField(min_length=10, max_length=5000)
    approved_items = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
    )


class ReturnRejectSerializer(serializers.Serializer):
    """UC-RET-02 reject."""

    justification = serializers.CharField(min_length=10, max_length=5000)


class ReturnInfoRequestSerializer(serializers.Serializer):
    """UC-RET-02 Alt B — request info."""

    message = serializers.CharField(min_length=10, max_length=5000)


# ────────────────────────────── UC-RET-03 (reception) ──────────────────────────────
class ReturnReceptionSerializer(serializers.Serializer):
    """UC-RET-03 — registra recepcion."""

    product_condition = serializers.ChoiceField(
        choices=ReturnItem.Condition.choices,
    )
    received_at = serializers.DateTimeField(required=False)
    observations = serializers.CharField(
        required=False, allow_blank=True, max_length=500, default='',
    )


# ────────────────────────────── UC-RET-06 (refund) ───────────────────────────────────
class ReturnRefundSerializer(serializers.Serializer):
    """UC-RET-06 — registra reembolso."""

    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0.01'),
    )


# ──────────────────── aliases para compatibilidad con views ────────────────────────
ReturnRequestSerializer = ReturnDetailSerializer


class ReturnRequestAdminSerializer(AdminReturnListSerializer):
    """Admin detail view — extends list serializer with items and history."""
    items   = ReturnItemSerializer(many=True, read_only=True)
    history = serializers.SerializerMethodField()

    class Meta(AdminReturnListSerializer.Meta):
        fields = AdminReturnListSerializer.Meta.fields + [
            'items', 'history', 'rejection_reason', 'description',
            'refund_at', 'refund_amount',
        ]

    def get_history(self, obj) -> list:
        qs = obj.history_entries.all().order_by('-created_at')
        return ReturnHistoryEntrySerializer(qs, many=True).data
