"""CompanySetting — configuración clave/valor per-empresa (L3).

TRANSITORIO en ``base`` (hogar heredado de la disolución de ``platform``).
La forma fiel a la referencia (19c) NO es un modelo centralizado: es
``company_dependent=True`` en el campo del addon dueño de cada clave
(``odoo19c:``, 23 archivos medidos) — ``ir.property`` ya no existe ni en
18c ni en 19c. La disolución clave-por-clave es D-5
(``analisis-disolucion-platform``); mientras, el mecanismo es abstracto
(FK ``company`` + clave + valor, sin tenants nombrados) y por eso puede
vivir aquí sin acoplar ``base``.
"""

import fields
import models

from addons.base.models.ir_rule import RuleScopedManager
from addons.base.models.res_company import ResCompany
from addons.base.models.timestamped_mixin import TimeStampedModel
from orm.environments import company_scope, get_current_company


class CompanySetting(TimeStampedModel):
    """Almacén de pares clave/valor de configuración **per-empresa** (L3).

    Diseño: :ref:`analisis-estrategia-configuracion-capas` (capa L3, sección
    7). Cierra :ref:`hallazgos-implementar-systemparameter-l2` (H-CFG-IMPL-10).
    Extiende el patrón L2 de ``addons.base.SystemParameter`` (equivalente
    Django de ``ir.config_parameter``: store key/value) a la dimensión
    per-compañía, con FK ``company`` + ``RuleScopedManager`` (SOL-085) —
    el mismo par ``objects``/``scoped`` que ``CompanyModuleSubscription``.

    Bajo DB-per-company (SOL-091) este es un modelo de **dominio**: el
    ``CompanyDatabaseRouter`` lo enruta a ``company_<N>_db`` cuando esa base
    existe (N>1) y degenera a ``default`` bajo N=1 (no está en
    ``MULTIDB_CONTROL_PLANE_APPS`` — ``company`` ya es dominio ahí, igual que
    ``Company``/``CompanyModuleSubscription``). La FK ``company`` se conserva
    en AMBOS regímenes: bajo N=1 (o incluso bajo N>1, ver
    ``TestSol085RowScopingIntraBase`` en
    ``tests/integration/platform/test_multidb_isolation.py``) varias
    empresas pueden co-residir en la misma base física — el aislamiento de
    fila (SOL-085) es una capa distinta y necesaria además del aislamiento
    por base (SOL-091), no redundante con él.

    **L0 (Kaupamex, operador) vs L1 (PracticaYoruba, el de ejemplo).**
    PracticaYoruba es un **tenant L1** (``FOUNDER_COMPANY_CODE``), NO L0 —
    Kaupamex es L0 (el operador de la plataforma). Por eso los valores
    ``hola@practicayoruba.com`` / ``newsletter@practicayoruba.com`` (antes
    ``default=`` de ``config.settings.base``) NO eran stale: son la config
    **L1 correcta** de ese tenant, y la migración ``0006`` los siembra como
    filas de ``CompanySetting`` de PracticaYoruba (no los reemplaza por un
    valor de Kaupamex). El fallback de ``get_setting`` (sin empresa activa o
    sin fila para esa empresa) sí es **neutral, nivel Kaupamex** —
    PracticaYoruba es solo uno de potencialmente varios tenants. Contrástese
    con L2 (``addons.base.SystemParameter``): ``backup.alert_email`` →
    ``admin@kaupamex.com`` es correcto ahí porque el alertamiento de backups
    es infra **L0** (plataforma), sin dimensión de empresa — a diferencia de
    contacto/newsletter, que sí son per-tenant.
    """

    company = fields.Many2one(
        ResCompany, on_delete=models.CASCADE, related_name='settings',
        verbose_name='Empresa',
    )
    key = fields.Char(max_length=255, verbose_name='Clave')
    value = fields.Text(verbose_name='Valor')

    objects = models.Manager()               # cross-company (L0 admin)
    scoped = RuleScopedManager()             # L3: record rules (ir_rule)

    class Meta:
        db_table = 'company_setting'
        verbose_name = 'Configuración de empresa'
        verbose_name_plural = 'Configuraciones de empresa'
        ordering = ['company_id', 'key']
        unique_together = [('company', 'key')]

    def __str__(self):
        return f'{self.company_id}:{self.key}'

    @staticmethod
    def _resolve_company_id(company):
        """``company`` puede ser ``None`` (usa la empresa ambiente del
        contexto), una instancia ``Company``, o un pk. Devuelve el pk o
        ``None`` si no hay empresa resoluble."""
        if company is None:
            return get_current_company()
        if isinstance(company, ResCompany):
            return company.pk
        return company

    @classmethod
    def get_setting(cls, key, default=None, company=None):
        """Devuelve el valor de ``key`` de ``company`` (o de la empresa
        ambiente del contexto si ``company`` es ``None``), o ``default`` si
        no hay empresa resoluble o no existe la fila.

        A diferencia de ``SystemParameter.get_param`` (L2, sin dimensión de
        empresa), "sin empresa resoluble" es un caso legítimo aquí — no un
        error — mientras el resolutor subdominio→company (UC-PLT-06) no
        exista: un request anónimo sin empresa en contexto cae a ``default``
        sin tocar la BD.

        Envuelve la consulta en ``company_scope(company_id)`` para que el
        ``CompanyDatabaseRouter`` enrute a la base correcta aun si se llama
        con un ``company`` explícito distinto de (o fuera de) la empresa
        ambiente (p. ej. desde un job sin contexto de request).
        """
        company_id = cls._resolve_company_id(company)
        if company_id is None:
            return default
        with company_scope(company_id):
            value = (cls.objects
                     .filter(company_id=company_id, key=key)
                     .values_list('value', flat=True)
                     .first())
        return value if value is not None else default

    @classmethod
    def set_setting(cls, key, value, company):
        """Fija ``value`` para ``key`` de ``company``. ``company`` es
        **obligatorio** (a diferencia de ``get_setting``): no existe un "de
        qué empresa" ambiente razonable al escribir configuración.
        """
        company_id = cls._resolve_company_id(company)
        if company_id is None:
            raise ValueError(
                'CompanySetting.set_setting requiere una empresa resoluble '
                '(pasar company= explícito o tener company_scope activo).'
            )
        with company_scope(company_id):
            obj, created = cls.objects.get_or_create(
                company_id=company_id, key=key, defaults={'value': str(value)},
            )
            if not created and obj.value != str(value):
                obj.value = str(value)
                obj.save(update_fields=['value', 'updated_at'])
        return obj
