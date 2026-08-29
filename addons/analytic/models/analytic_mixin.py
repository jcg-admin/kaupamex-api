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

Lo que SI se porta desde este pase (tarea **#526**) — el eje de BUSQUEDA:
``analytic_precision``, ``_query_analytic_accounts``,
``_compute_analytic_distribution``, ``_search_analytic_distribution``,
``_search_distribution_analytic_account_ids`` y el indice GIN de ``init()``,
que baja a una migracion del consumidor concreto
(``analytic_distribution_gin_index_sql``).

**Por que se portan ahora y no antes.** Su ausencia se declaraba "gap de
alcance" citando limitaciones de MariaDB. Esa premisa es falsa desde ADR-028:
el motor es PostgreSQL 16, que trae los cuatro constructos que la referencia
usa —``jsonb_path_query_array``, ``regexp_split_to_array``, el operador ``&&``
de solapamiento y el indice GIN funcional— sin rodeo alguno. El bloque que
razonaba sobre ``JSON_KEYS``, ``JSON_OVERLAPS``, ``GeneratedField`` y
``FULLTEXT`` se retira entero: describia un motor que este arbol ya no usa
(Clausula 2 del principio rector — estado heredado incorrecto se corrige en el
pase que lo encuentra, no se difiere).

Lo que NO se porta — **divergencia de mecanismo declarada**:
``_read_group_groupby``, ``_read_group_select`` y ``_get_count_id`` construyen
el "group by" del cliente web de Odoo sobre el JSON; su consumidor es la vista
de lista de ese cliente, que este arbol no sirve. ``filtered_domain`` opera
sobre el framework de dominios en memoria del ORM fuente. Y
``_validate_distribution`` depende de ``get_relevant_plans``, que a su vez
depende del sistema de columna por plan de ``analytic_plan.py``.

"""
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.contrib.postgres.fields import ArrayField
from django.db.models import BooleanField, Q, TextField
from django.db.models.expressions import RawSQL

import fields
import models

from addons.base.models import DecimalPrecision
from tools.sql import SQL

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

    @property
    def analytic_precision(self):
        """Los digitos con que se redondea el porcentaje -- ≙ ``:22-25``.

        La fuente lo declara ``fields.Integer(store=False, default=lambda ...)``.
        Un campo no persistido cuyo valor sale de otra tabla es una ``property``
        aqui; el ``default`` invocable de la fuente se vuelve el cuerpo.
        """
        precision = DecimalPrecision.objects.filter(
            name='Percentage Analytic',
        ).first()
        return precision.digits if precision else 2

    # -- busqueda por cuenta analitica sobre el JSON --------------------------

    @classmethod
    def _query_analytic_accounts(cls, table=None):
        """El arreglo de IDs de cuenta que la distribucion contiene -- ≙ ``:42-47``.

        Verbatim de la fuente: ``jsonb_path_query_array`` extrae las claves del
        objeto y ``regexp_split_to_array`` parte la clave compuesta
        (``"3,7"``) por todo lo que no sea digito. El resultado es ``text[]``,
        que es lo que el operador ``&&`` de solapamiento compara.
        """
        column = f'"{table or cls._meta.db_table}"."analytic_distribution"'
        return SQL(
            r"""regexp_split_to_array("""
            rf"""jsonb_path_query_array({column}, '$.keyvalue()."key"')::text, '\D+')""",
            output_field=ArrayField(TextField()),
        )

    @classmethod
    def analytic_distribution_gin_index_sql(cls, table=None):
        """El DDL del indice GIN -- ≙ ``init()`` (``:32-40``).

        La fuente lo emite en ``init()``, el gancho que su ORM invoca al
        instalar el modulo. Aqui el hogar de un DDL es una migracion, asi que
        el mixin publica la sentencia y el modelo concreto la emite con
        ``RunSQL``. El ``IF NOT EXISTS`` la deja idempotente, igual que alla.
        """
        name = table or cls._meta.db_table
        return (
            f'CREATE INDEX IF NOT EXISTS '
            f'{name}_analytic_distribution_accounts_gin_index '
            f'ON "{name}" USING gin(regexp_split_to_array('
            f'jsonb_path_query_array("analytic_distribution", '
            f"'$.keyvalue().\"key\"')::text, '\\D+'))"
        )

    def _compute_analytic_distribution(self):
        """≙ ``_compute_analytic_distribution`` (``:77-78``) -- cuerpo vacio.

        La fuente lo declara para que el campo sea ``compute=`` + ``store=True``
        + ``readonly=False``: el compute no calcula nada, existe para que el ORM
        acepte la escritura manual sobre un campo almacenado. Aqui el campo es
        editable por construccion, asi que el simbolo se porta con el mismo
        cuerpo que la fuente le da.
        """

    @classmethod
    def _search_analytic_distribution(cls, operator, value, table=None):
        """≙ ``_search_analytic_distribution`` (``:80-124``).

        Traduce ``('analytic_distribution', <op>, <valor>)`` a un ``Q``
        aplicable con ``filter()``. El valor admite IDs de cuenta o nombres:

        - ``in`` / ``not in`` con enteros -> se usan tal cual;
        - ``in`` / ``not in`` con cadenas -> se resuelven por nombre exacto;
        - ``ilike`` / ``not ilike`` -> se resuelven por nombre parcial y el
          operador colapsa a ``in``/``not in``, como en la fuente.

        La rama negativa incluye ``OR analytic_distribution IS NULL`` porque el
        solapamiento de un NULL no es falso sino nulo -- verbatim de ``:118-123``.
        """
        if operator in ('ilike', 'not ilike'):
            ids = list(AccountAnalyticAccount.objects.filter(
                name__icontains=value).values_list('pk', flat=True))
            operator = 'not in' if operator.startswith('not') else 'in'
        elif operator in ('in', 'not in'):
            ids = []
            for item in value:
                if isinstance(item, str):
                    ids.extend(AccountAnalyticAccount.objects.filter(
                        name=item).values_list('pk', flat=True))
                else:
                    ids.append(item)
        else:
            raise ValueError(f'ANALYTIC_DISTRIBUTION_OPERATOR_NOT_SUPPORTED: {operator}')

        if not ids:
            # ≙ ``return Domain(operator == 'not in')`` (``:110-112``) -- la
            # fuente optimiza a una constante; el equivalente es un Q que no
            # filtra nada (verdadero) o que no admite nada (falso).
            return Q() if operator == 'not in' else Q(pk__in=[])

        keys = [str(account_id) for account_id in ids if account_id]
        column = f'"{table or cls._meta.db_table}"."analytic_distribution"'
        overlap = (
            r"""regexp_split_to_array("""
            rf"""jsonb_path_query_array({column}, '$.keyvalue()."key"')::text, '\D+')"""
            """ && %s"""
        )
        if operator == 'in':
            return Q(RawSQL(overlap, [keys], output_field=BooleanField()))
        return Q(RawSQL(
            f'(NOT {overlap} OR {column} IS NULL)',
            [keys], output_field=BooleanField(),
        ))

    @classmethod
    def _search_distribution_analytic_account_ids(cls, operator, value, table=None):
        """≙ ``_search_distribution_analytic_account_ids`` (``:66-75``).

        La fuente traduce los operadores de subconsulta (``any``/``not any``)
        resolviendolos a IDs y delegando en el campo Json. Aqui el equivalente
        de una subconsulta es un ``QuerySet``, y el de un dominio, un ``Q``.
        """
        if operator in ('any', 'not any'):
            if isinstance(value, Q):
                value = list(AccountAnalyticAccount.objects.filter(
                    value).values_list('pk', flat=True))
            elif isinstance(value, models.QuerySet):
                value = list(value.values_list('pk', flat=True))
            else:
                return NotImplemented
            operator = 'in' if operator == 'any' else 'not in'
        return cls._search_analytic_distribution(operator, value, table=table)

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
