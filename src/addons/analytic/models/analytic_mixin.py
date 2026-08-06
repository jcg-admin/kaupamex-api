"""``analytic.mixin`` (Odoo ``analytic``).

Adaptación fiel de Odoo analytic/models/analytic_mixin.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3). Mixin abstracto reutilizable que
OTROS modelos de negocio (línea de orden de venta, línea de factura...)
heredarían para adjuntar una distribución analítica libre —N cuentas con
porcentaje cada una— **independiente** del sistema de columna por plan de
``analytic_plan.py``/``analytic_line.py``. Hoy ningún addon de este árbol lo
usa todavía (``project.project`` explícitamente omite la analítica, ver
``src/addons/project/models/project_project.py:6``); se porta el mixin en sí
para que un futuro consumidor (``sale.order.line``, ``account.move.line``)
lo herede sin reabrir este addon.

Lo que SÍ se porta — Python puro, sin SQL de motor: ``analytic_distribution``
(``Json``), ``_get_analytic_account_ids_from_distributions``,
``distribution_analytic_account_ids`` (antes ``_compute_...``, aquí
``@property``), sanitización de porcentajes (antes ``create``/``write``
overrides con ``vals`` dict — aquí unificado en ``save()``, el único punto de
persistencia de Django) y el algoritmo completo de fusión
(``_modifiying_distribution_values`` + ``_merge_distribution``).

**Adaptación del algoritmo de fusión** (única desviación de comportamiento,
no sólo de forma): en la referencia, la clave ``__update__`` de
``new_distribution`` lleva **nombres de columna** de los planes que cambian
(``x_plan3_id``, ...) porque cada plan raíz tiene su propia columna. Sin ese
sistema (ver ``analytic_plan.py``), no hay nombres de columna que enumerar.
Aquí ``__update__`` lleva **PKs de plan raíz** (``AccountAnalyticPlan.root``)
en su lugar — mismo propósito (marcar qué planes se están redistribuyendo
intencionalmente), mismo álgebra de razones, distinto identificador.

Lo que NO se porta — **Postgres-only, no aplica a MariaDB**: ``init()``
(índice GIN sobre ``jsonb_path_query_array`` — función de Postgres),
``_query_analytic_accounts`` (``regexp_split_to_array``/``jsonb_path_query_array``,
ídem), ``_search_analytic_distribution``, ``_read_group_groupby``,
``_read_group_select``, ``_get_count_id`` (agregación de "group by" del
cliente web de Odoo sobre JSON, construida con SQL crudo de Postgres). Este
proyecto usa MariaDB (``config/settings/base.py``); una búsqueda/agrupación
equivalente sobre JSON en MariaDB necesitaría su propio diseño
(``JSON_TABLE`` o columnas generadas), fuera de alcance de este corte —
declarado, no inventado. Tampoco se porta ``filtered_domain`` (framework de
dominios Python del ORM de Odoo, sin análogo) ni ``_validate_distribution``
(depende de ``get_relevant_plans``, ver ``analytic_plan.py``).
"""
from collections import defaultdict

from django.core.exceptions import ValidationError

import fields
import models

from addons.base.models import DecimalPrecision

from .analytic_account import AccountAnalyticAccount


class AnalyticMixin(models.Model):
    """``analytic.mixin`` — distribución analítica libre (N cuentas, %)."""

    analytic_distribution = fields.Json(
        null=True, blank=True, default=dict,
        verbose_name='Distribución analítica',
        help_text='Odoo analytic_distribution: {"id1,id2,...": porcentaje}.',
    )

    class Meta:
        abstract = True

    # -- lectura -------------------------------------------------------------

    @staticmethod
    def _get_analytic_account_ids_from_distributions(distributions):
        """Fiel a ``_get_analytic_account_ids_from_distributions``
        (odoo19c: líneas 48-56)."""
        if not distributions:
            return set()
        if isinstance(distributions, (list, tuple, set)):
            return {
                int(_id)
                for distribution in distributions
                for key in (distribution or {})
                for _id in key.split(',')
            }
        return {int(_id) for key in (distributions or {}) for _id in key.split(',')}

    @property
    def distribution_analytic_account_ids(self):
        """Fiel a ``_compute_distribution_analytic_account_ids`` (odoo19c:
        líneas 58-64), como ``@property`` (no stored — ver docstring del
        módulo)."""
        ids = []
        seen = set()
        for key in (self.analytic_distribution or {}):
            for raw_id in key.split(','):
                if raw_id.isdigit() and int(raw_id) not in seen:
                    seen.add(int(raw_id))
                    ids.append(int(raw_id))
        return AccountAnalyticAccount.objects.filter(pk__in=ids)

    # -- persistencia (Odoo create/write -> Django save) ---------------------

    def save(self, *args, **kwargs):
        """Normaliza los porcentajes antes de guardar — fiel a ``write``/
        ``create`` (odoo19c: líneas 169-180), unificados en ``save()``."""
        self._sanitize_distribution()
        super().save(*args, **kwargs)

    def _sanitize_distribution(self):
        """Fiel a ``_sanitize_values`` (odoo19c: líneas 198-205)."""
        if not self.analytic_distribution:
            return
        precision = DecimalPrecision.objects.filter(
            name='Percentage Analytic',
        ).first()
        digits = precision.digits if precision else 2
        self.analytic_distribution = {
            account_id: (
                round(distribution, digits)
                if account_id != '__update__' else distribution
            )
            for account_id, distribution in self.analytic_distribution.items()
        }

    def clean(self):
        super().clean()
        if self.analytic_distribution:
            for account_id, pct in self.analytic_distribution.items():
                if account_id == '__update__':
                    continue
                if not isinstance(pct, (int, float)):
                    raise ValidationError({
                        'analytic_distribution': 'ANALYTIC_DISTRIBUTION_PERCENT_NOT_NUMERIC',
                    })

    # -- fusión de distribuciones ---------------------------------------------

    @staticmethod
    def _modifiying_distribution_values(old_distribution, new_distribution):
        """Fiel a ``_modifiying_distribution_values`` (odoo19c: líneas
        207-242) — ver docstring del módulo para la adaptación de
        ``__update__`` (PKs de plan raíz, no nombres de columna)."""
        root_plan_ids_to_update = set(new_distribution.pop('__update__', ()) or ())
        old_distribution = dict(old_distribution or {})
        old_distribution.pop('__update__', None)

        non_changing_values = defaultdict(float)
        non_changing_amount = 0
        for old_key, old_val in old_distribution.items():
            account_ids = [int(aid) for aid in old_key.split(',') if aid]
            accounts = AccountAnalyticAccount.objects.filter(
                pk__in=account_ids,
            ).select_related('plan')
            remaining_key = tuple(sorted(
                account.pk for account in accounts
                if account.plan.root.pk not in root_plan_ids_to_update
            ))
            if remaining_key:
                non_changing_values[remaining_key] += old_val
                non_changing_amount += old_val

        changing_values = defaultdict(float)
        changing_amount = 0
        for new_key, new_val in new_distribution.items():
            account_ids = [int(aid) for aid in new_key.split(',') if aid]
            accounts = AccountAnalyticAccount.objects.filter(
                pk__in=account_ids,
            ).select_related('plan')
            remaining_key = tuple(sorted(
                account.pk for account in accounts
                if account.plan.root.pk in root_plan_ids_to_update
            ))
            if remaining_key:
                changing_values[remaining_key] += new_val
                changing_amount += new_val

        return non_changing_values, changing_values, non_changing_amount, changing_amount

    @staticmethod
    def _merge_distribution(old_distribution, new_distribution):
        """Fiel a ``_merge_distribution`` (odoo19c: líneas 244-275)."""
        if '__update__' not in (new_distribution or {}):
            return new_distribution  # actualiza todo por defecto

        (non_changing_values, changing_values,
         non_changing_amount, changing_amount) = (
            AnalyticMixin._modifiying_distribution_values(
                old_distribution, new_distribution,
            )
        )

        if non_changing_amount > changing_amount:
            ratio = changing_amount / non_changing_amount
            additional_vals = {
                ','.join(map(str, old_key)): old_val * (1 - ratio)
                for old_key, old_val in non_changing_values.items()
                if old_key
            }
            ratio = 1
        elif changing_amount > non_changing_amount:
            ratio = non_changing_amount / changing_amount
            additional_vals = {
                ','.join(map(str, new_key)): new_val * (1 - ratio)
                for new_key, new_val in changing_values.items()
                if new_key
            }
        else:
            ratio = 1
            additional_vals = {}

        merged = {
            ','.join(map(str, old_key + new_key)): ratio * old_val * new_val / non_changing_amount
            for old_key, old_val in non_changing_values.items()
            for new_key, new_val in changing_values.items()
        }
        return merged | additional_vals
