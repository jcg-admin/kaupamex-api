"""Company — el cliente/organización que contrata Kaupamex (raíz L1, DEC-T7).

Parte de ``addons.platform`` — capa L1 de la plataforma Kaupamex.
Layout ``models/`` (un archivo por modelo), espejo de odoo-tools.
"""

from django.utils import timezone
import fields
import models

from addons.base.models import TimeStampedModel
from addons.base_vat.validators import validate_rfc
from addons.platform.context import get_current_company


class CompanyScopedManager(models.Manager):
    """Manager de aislamiento de fila L3 (SOL-085). ``for_current_company()``
    filtra por la ``Company`` del contexto del request, **fail-closed**: sin
    company en contexto → queryset vacío (denegar por defecto), nunca "todo".

    Requiere que el modelo tenga una FK ``company`` (columna ``company_id``).
    El acceso cross-company del operador L0 usa el manager por defecto
    (``objects``), explícito y no ambiguo.
    """

    def for_current_company(self):
        company_id = get_current_company()
        if company_id is None:
            return self.get_queryset().none()
        return self.get_queryset().filter(company_id=company_id)


# Códigos canónicos de companies especiales (SOL-085 S3, lección L-EXT-3).
# - Founder: primer tenant L1 real (PracticaYoruba); target de backfill de las
#   filas de dominio existentes al colgar la FK ``company`` (S3).
# - System: company de datos compartidos de plataforma (``is_system=True``);
#   los datos globales (SEPOMEX, referencia) cuelgan de aquí, con fallback por
#   whitelist en el manager scopeado — NO ``company_id`` nullable.
FOUNDER_COMPANY_CODE = 'practicayoruba'
SYSTEM_COMPANY_CODE = 'kaupamex_global'

# Valores L1 de contacto/newsletter/transaccional de PracticaYoruba (founder
# tenant, SOL-090 slice 3 + follow-up #199), sembrados como sus propios
# ``CompanySetting`` por las migraciones de datos
# ``company/0006_seed_founder_settings`` (contacto/newsletter) y
# ``company/0007_seed_founder_notifications_from`` (transaccional). Tal cual
# existían en ``config.settings.base`` (``CONTACT_FROM_EMAIL``/
# ``CONTACT_NOTIFY_EMAIL``/``NEWSLETTER_FROM_EMAIL``/``DEFAULT_FROM_EMAIL``)
# antes de estas slices — PracticaYoruba es tenant L1 (NO L0/Kaupamex), así
# que no eran stale, sólo estaban mal ubicados como ``default=`` global.
#
# ``notifications.from_email`` es el remitente **no-reply transaccional único**
# del tenant: bajo el diseño previo TODO el correo transaccional (auth,
# órdenes, envíos, devoluciones, soporte) salía de un solo ``DEFAULT_FROM_EMAIL``
# (``noreply@``). Se conserva esa unicidad como una sola clave per-tenant, en
# vez de una clave por addon.
#
# Constante módulo-nivel (dato, no comportamiento) para que la migración y los
# tests reseed la compartan sin duplicarla (mismo patrón que
# ``_DEFAULT_PARAMETERS`` en ``addons.base.models``).
FOUNDER_L1_SETTINGS = {
    'contact.from_email': 'hola@practicayoruba.com',
    'contact.notify_email': 'hola@practicayoruba.com',
    'newsletter.from_email': 'newsletter@practicayoruba.com',
    'notifications.from_email': 'noreply@practicayoruba.com',
}


class Company(TimeStampedModel):
    """Cliente/organización que contrata la plataforma (raíz L1, DEC-T7)."""

    class Status(models.TextChoices):
        TRIAL = 'trial', 'En prueba'
        ACTIVE = 'active', 'Activo'
        SUSPENDED = 'suspended', 'Suspendido'
        CANCELLED = 'cancelled', 'Cancelado'

    code = models.SlugField(max_length=50, unique=True, verbose_name='Código')
    name = fields.Char(max_length=150, verbose_name='Nombre')
    status = fields.Selection(
        max_length=12, choices=Status.choices, default=Status.TRIAL,
        verbose_name='Estado',
    )
    # Company de datos compartidos de plataforma (L-EXT-3). Los datos globales
    # cuelgan de la system company; el manager scopeado hace fallback por
    # whitelist a ella además de la company activa. NO usar company nullable.
    is_system = fields.Boolean(
        default=False, verbose_name='Company de sistema',
        help_text='Company de datos compartidos de plataforma (L0), no un tenant.',
    )
    # Datos mínimos de facturación (opcionales hasta activar).
    billing_email = models.EmailField(blank=True, default='', verbose_name='Correo de facturación')
    billing_name = fields.Char(max_length=150, blank=True, default='', verbose_name='Razón social')
    tax_id = fields.Char(
        max_length=30, blank=True, default='', verbose_name='RFC / Tax ID',
        validators=[validate_rfc],
        help_text='RFC del SAT (12 moral / 13 física). Validado por base_vat.',
    )

    class Meta:
        db_table = 'company'
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'
        ordering = ['code']

    def __str__(self):
        return self.code

    @classmethod
    def get_founder(cls):
        """Founder company (PracticaYoruba) — target de backfill de S3. Idempotente."""
        obj, _ = cls.objects.get_or_create(
            code=FOUNDER_COMPANY_CODE,
            defaults={'name': 'PracticaYoruba', 'status': cls.Status.ACTIVE},
        )
        return obj

    @classmethod
    def get_system(cls):
        """System company (datos compartidos de plataforma, L-EXT-3). Idempotente."""
        obj, _ = cls.objects.get_or_create(
            code=SYSTEM_COMPANY_CODE,
            defaults={'name': 'Kaupamex (plataforma)', 'status': cls.Status.ACTIVE,
                      'is_system': True},
        )
        return obj

    def active_module_codes(self, now=None):
        """Set de ``Module.code`` con suscripción **activa** (L1-a).

        El resolver compone esto: ``caps L2 filtradas por
        c.module in company.active_module_codes()``.
        """
        if now is None:
            now = timezone.now()
        codes = set()
        for sub in self.subscriptions.select_related('module').all():
            if sub.is_active(now):
                codes.add(sub.module.code)
        return codes
