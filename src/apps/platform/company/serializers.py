"""Serializers — apps.platform.company (consola L0 del operador Kaupamex).

Solo lectura del directorio de companies L1 (UC-PLT-12). El detalle expone el
estado de la company + resumen de módulos activos y conteo de usuarios, sin
datos sensibles de otras companies (el operador L0 es cross-company por
definición).
"""
from rest_framework import serializers

from apps.platform.company.models import Company, CompanyModuleSubscription


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
            'status', 'started_at', 'expires_at', 'price',
            'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'company_code', 'module_code', 'is_active', 'created_at']

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
