"""Serializers — apps.platform.company (consola L0 del operador Kaupamex).

Solo lectura del directorio de companies L1 (UC-PLT-12). El detalle expone el
estado de la company + resumen de módulos activos y conteo de usuarios, sin
datos sensibles de otras companies (el operador L0 es cross-company por
definición).
"""
from rest_framework import serializers

from apps.platform.authz.models import Module
from apps.platform.company.models import (
    Company,
    CompanyModuleSubscription,
    ModulePrice,
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
    """Fila/detalle de una company en el directorio del operador (read-only)."""

    active_modules = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Company
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
