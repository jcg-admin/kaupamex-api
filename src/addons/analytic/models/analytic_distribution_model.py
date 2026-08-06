"""``account.analytic.distribution.model`` (Odoo ``analytic``).

Adaptación fiel de Odoo analytic/models/analytic_distribution_model.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

Lo que SÍ se porta: ``sequence``, ``partner``, ``company`` (sin
``partner_category_id`` — ver más abajo), y la lógica completa de
``_get_distribution``/``_get_applicable_models``/``_create_domain`` — Python
puro, adaptado a ``QuerySet``/``Q`` de Django en vez de dominios de Odoo.

``partner_category_id`` (M2M a ``res.partner.category``) NO se porta: este
árbol no tiene un modelo ``res.partner.category`` portado todavía (medido:
``grep -rl "PartnerCategory" src/addons/*/models/*.py`` → 0 hits). Es un GAP
declarado, no un descarte deliberado — cuando ``res.partner.category``
aterrice, el campo M2M y su rama en ``_create_domain`` se agregan en una
migración aditiva.

``_check_company_accounts`` (constraint de compañía sobre las cuentas de la
distribución) NO se porta: usa SQL crudo de Postgres
(``jsonb_path_query_array``/``ARRAY[...]::text[] && ...``, vía
``_query_analytic_accounts`` de ``analytic.mixin``) — mismo motivo de
``analytic_mixin.py`` (proyecto en MariaDB, no Postgres).
"""
import fields
import models

from addons.base.models import TimeStampedModel

from .analytic_mixin import AnalyticMixin


class AccountAnalyticDistributionModel(AnalyticMixin, TimeStampedModel):
    """``account.analytic.distribution.model`` — regla de prellenado de
    distribución analítica por contacto/compañía."""

    sequence = fields.Integer(default=10, verbose_name='Secuencia')
    partner = fields.Many2one(
        'base.ResPartner', on_delete=models.CASCADE, null=True, blank=True,
        related_name='analytic_distribution_models', verbose_name='Contacto',
        help_text=(
            'Odoo partner_id (ondelete=cascade). Selecciona un contacto '
            'para el que se usa esta distribución.'
        ),
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, null=True, blank=True,
        related_name='analytic_distribution_models', verbose_name='Empresa',
        help_text='Odoo company_id (ondelete=cascade).',
    )

    class Meta:
        db_table = 'account_analytic_distribution_model'
        ordering = ['sequence', '-id']
        verbose_name = 'Modelo de distribución analítica'
        verbose_name_plural = 'Modelos de distribución analítica'
        # ADDON NO INSTALADO TODAVÍA — ver el comentario extenso en
        # ``analytic_plan.py::AccountAnalyticPlan.Meta`` (mismo precedente
        # que ``onboarding``).
        app_label = 'analytic'

    def __str__(self):
        return f'Distribución analítica #{self.pk}' if self.pk else 'Distribución analítica (nueva)'

    # -- selección de modelo aplicable ---------------------------------------

    @classmethod
    def _get_default_search_domain_vals(cls):
        """Fiel a ``_get_default_search_domain_vals`` (odoo19c: líneas
        78-84), sin ``partner_category_id`` (ver docstring del módulo)."""
        return {'company_id': None, 'partner_id': None}

    @staticmethod
    def _create_domain(fname, value):
        """Fiel a ``_create_domain`` (odoo19c: líneas 94-99), sin la rama
        ``partner_category_id``.

        Odoo ``[(fname, 'in', [value, False])]`` == "coincide con ``value``
        O está sin establecer". En SQL, ``field IN (value, NULL)`` NO
        atrapa las filas NULL (lógica de tres valores) — de ahí el ``Q``
        explícito con ``isnull``, en vez de traducir el dominio literal.
        """
        if value is None:
            return models.Q(**{f'{fname}__isnull': True})
        return models.Q(**{fname: value}) | models.Q(**{f'{fname}__isnull': True})

    @classmethod
    def _get_applicable_models(cls, vals):
        """Fiel a ``_get_applicable_models`` (odoo19c: líneas 86-92)."""
        vals = cls._get_default_search_domain_vals() | vals
        query = models.Q()
        for fname, value in vals.items():
            query &= cls._create_domain(fname, value)
        return cls.objects.filter(query)

    @classmethod
    def _get_distribution(cls, vals):
        """Fiel a ``_get_distribution`` (odoo19c: líneas 60-76).

        ``applied_plans`` es un ``set`` de PKs de plan raíz (en la
        referencia es un recordset de ``account.analytic.plan`` — ver el
        docstring de ``analytic_mixin.py`` para la adaptación de
        ``__update__`` que este método alimenta).
        """
        applicable_models = cls._get_applicable_models({
            k: v for k, v in vals.items() if k != 'related_root_plan_ids'
        })
        res = {}
        applied_plans = set(vals.get('related_root_plan_ids') or ())
        for model in applicable_models:
            current_plans = {
                account.plan.root.pk
                for account in model.distribution_analytic_account_ids
            }
            if current_plans and not (applied_plans & current_plans):
                applied_plans |= current_plans
                res = cls._merge_distribution(res, dict(model.analytic_distribution or {}) | {
                    '__update__': list(current_plans),
                })
        return res
