"""Serializers — addons.sale_subscription (consola L0 del operador Kaupamex).

Solo lectura del directorio de companies L1 (UC-PLT-12). El detalle expone el
estado de la company + resumen de módulos activos y conteo de usuarios, sin
datos sensibles de otras companies (el operador L0 es cross-company por
definición).
"""
from rest_framework import serializers

from addons.authz.models import Module
from addons.base.models import ResCompany
from addons.sale_subscription.models import (
    CompanyModuleSubscription,
    ModulePrice,
    SubscriptionBillingRun,
    SubscriptionInvoice,
)


class ModulePriceSerializer(serializers.ModelSerializer):
    """Tarifa L0 por módulo × ciclo (catálogo de precios, DEC-T6, S4).

    El operador Kaupamex la siembra/versiona; ``module_code`` es de solo
    lectura para pintar el catálogo sin resolver el id.
    """

    module_code = serializers.CharField(source='module.code', read_only=True)

    class Meta:
        model = ModulePrice
        fields = [
            'id', 'module', 'module_code', 'billing_cycle', 'price',
            'currency', 'effective_from', 'effective_to', 'created_at',
        ]
        read_only_fields = ['id', 'module_code', 'created_at']


class ModuleCatalogSerializer(serializers.ModelSerializer):
    """Fila del catálogo L0 de módulos (read-only, #179).

    Expone la metadata de catálogo del ``Module`` (contrato ``__manifest__``)
    que la consola del operador consume para pintar los módulos contratables:
    ``code``/``name``, ``is_application`` (vendible vs técnico), ``tier``,
    ``category``, ``version``, ``description``, ``depends`` (por código) e
    ``is_active``.
    """

    depends = serializers.SlugRelatedField(
        slug_field='code', many=True, read_only=True,
    )

    class Meta:
        model = Module
        fields = [
            'id', 'code', 'name', 'is_application', 'tier', 'category',
            'version', 'description', 'depends', 'is_active',
        ]
        read_only_fields = fields


class CompanySerializer(serializers.ModelSerializer):
    """Fila/detalle de una company en el directorio del operador (read-only).

    ``name``/``billing_name``/``tax_id`` son propiedades delegadas al partner
    (fiel a la referencia: la identidad vive en ``res.partner``), así que se
    declaran explícitas — ModelSerializer no infiere propiedades.
    """

    name = serializers.CharField(read_only=True)
    billing_name = serializers.CharField(read_only=True)
    tax_id = serializers.CharField(source='vat', read_only=True)
    active_modules = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = ResCompany
        fields = [
            'id', 'code', 'name', 'status',
            'billing_email', 'billing_name', 'tax_id',
            'active_modules', 'user_count', 'created_at',
        ]
        read_only_fields = fields

    def get_active_modules(self, obj):
        return sorted(obj.active_module_codes())

    def get_user_count(self, obj):
        return obj.users.count()


class CompanyCreateSerializer(serializers.ModelSerializer):
    """Alta de un tenant desde la consola L0 (UC-PLT-12).

    El estado inicial es SIEMPRE ``trial`` (fijo, no editable en alta —
    mockup ``consola-tenants``): el operador no puede crear un tenant ya
    activo. ``code`` es slug único (el ``UniqueValidator`` del modelo lo
    superficializa como 400 legible).
    """

    name = serializers.CharField(max_length=200)
    tax_id = serializers.CharField(
        max_length=32, required=False, allow_blank=True, default='')

    class Meta:
        model = ResCompany
        # ``billing_name`` ya no es columna: es la razón social de la entidad
        # comercial del partner (derivada) — no se captura en el alta.
        fields = ['id', 'code', 'name', 'billing_email', 'tax_id']

    def create(self, validated_data):
        validated_data['status'] = ResCompany.Status.TRIAL
        # ``tax_id`` vive en el partner (``vat``), como en la referencia.
        tax_id = validated_data.pop('tax_id', '')
        company = super().create(validated_data)
        if tax_id:
            company.partner.vat = tax_id
            company.partner.save(update_fields=['vat'])
        return company


class CompanyModuleSubscriptionSerializer(serializers.ModelSerializer):
    """Asignación de un módulo a una company (consola L0, SOL-085 S4).

    Escritura por ``company``/``module`` (PK); lectura expone los códigos y el
    estado ``is_active`` derivado. El guard de dependencias S3 se valida aquí
    (``validate``) para devolver 400 —no dejar que el ``save()`` del modelo
    lance un 500.
    """

    company_code = serializers.CharField(source='company.code', read_only=True)
    module_code = serializers.CharField(source='module.code', read_only=True)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = CompanyModuleSubscription
        fields = [
            'id', 'company', 'company_code', 'module', 'module_code',
            'status', 'started_at', 'expires_at', 'billing_cycle', 'price',
            'is_active', 'created_at',
        ]
        # ``price`` es DERIVADO: se copia del catálogo ``ModulePrice`` vigente
        # según ``billing_cycle`` al contratar (DEC-T6, S4) — no lo fija el
        # cliente, para que un cambio de tarifa no reescriba lo ya cobrado.
        read_only_fields = [
            'id', 'company_code', 'module_code', 'price', 'is_active', 'created_at',
        ]

    def create(self, validated_data):
        instance = CompanyModuleSubscription(**validated_data)
        instance.apply_current_price()
        instance.save()
        return instance

    def update(self, instance, validated_data):
        cycle_changed = (
            'billing_cycle' in validated_data
            and validated_data['billing_cycle'] != instance.billing_cycle
        )
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        # Re-copiar el precio solo si cambió el ciclo (re-cotización explícita);
        # un update que no toca el ciclo NO reescribe el precio congelado.
        if cycle_changed:
            instance.apply_current_price()
        instance.save()
        return instance

    def get_is_active(self, obj):
        return obj.is_active()

    def validate(self, attrs):
        # Guard S3: activar exige dependencias activas. Se construye una
        # instancia transitoria (con los campos ya validados + los actuales en
        # update) y se consulta missing_dependencies() -> 400 legible.
        instance = CompanyModuleSubscription(**{
            **{f: getattr(self.instance, f, None) for f in ('company', 'module', 'status')},
            **{k: v for k, v in attrs.items() if k in ('company', 'module', 'status')},
        }) if self.instance else CompanyModuleSubscription(**attrs)
        if instance.status == CompanyModuleSubscription.Status.ACTIVE and instance.company_id and instance.module_id:
            missing = instance.missing_dependencies()
            if missing:
                raise serializers.ValidationError({
                    'module': (
                        f"El módulo '{instance.module.code}' requiere módulos "
                        f"activos que la empresa no tiene: {', '.join(sorted(missing))}."
                    )
                })
        return attrs


class SubscriptionBillingRunSerializer(serializers.ModelSerializer):
    """Resumen de una corrida de facturación L0 (UC-PLT-18 §7C.2)."""

    run_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = SubscriptionBillingRun
        fields = [
            'run_id', 'period', 'triggered_by', 'invoices_issued',
            'amount_charged', 'currency', 'failures', 'started_at',
            'finished_at',
        ]
        read_only_fields = fields


class SubscriptionInvoiceSerializer(serializers.ModelSerializer):
    """Factura de suscripción L0 (documento de cobro por período, UC-PLT-18)."""

    company_code = serializers.CharField(source='company.code', read_only=True)
    module_code = serializers.CharField(
        source='subscription.module.code', read_only=True,
    )

    class Meta:
        model = SubscriptionInvoice
        fields = [
            'id', 'company', 'company_code', 'subscription', 'module_code',
            'run', 'period', 'amount', 'currency', 'status', 'issued_at',
            'paid_at', 'failure_reason', 'created_at',
        ]
        read_only_fields = fields
