"""Lo que ``account`` le cuelga a la divisa — ≙ ``_inherit`` (T-B2a).

Adaptación de ``addons/account/models/res_currency.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``).

**Los dos campos que T-B1 contó para este modelo no se portan** — y aun así
este archivo no está vacío, porque lo sustantivo de la extensión no es un
campo: es un **guard de integridad** que la referencia declara en la misma
clase.

Los dos campos, y qué los bloquea
==================================

- **``fiscal_country_codes``** (``odoo19c: res_currency.py:17``) mapea
  ``account_fiscal_country_id.code`` sobre las empresas permitidas. Ese campo
  pertenece al Bloque 1 (los 72 de ``res.company``) y está ausente — medido:
  ``grep -n "account_fiscal_country" base/models/res_company.py`` → 0 hits.
  **Lo cierra la tarea #137.**
- **``display_rounding_warning``** (``:15``) compara
  ``record._origin.rounding`` con ``record.rounding``: es el aviso que la
  vista de formulario de Odoo muestra **mientras se edita**, contrastando el
  valor en pantalla con el de la base. ``_origin`` es el pseudo-registro de
  ``onchange``; aquí no hay onchange de servidor, así que no hay análogo.
  **DESCONOCIDO declarado**, con su condición de cierre: se decide si alguna
  vez existe un canal equivalente (validar en el serializer contra el valor
  previo), no antes.

El guard sí se porta — con su ceguera declarada
===============================================

``odoo19c: res_currency.py:27-39`` impide **reducir los decimales** de una
divisa que ya generó apuntes. La razón es que ``rounding`` no es cosmético:
es el factor con el que ya se redondearon importes asentados. Bajarlo a
posteriori haría que la misma fila se leyera con otro valor que el que se
contabilizó.

*Métrica:* el guard consulta si existe algún apunte con esta divisa.
*Ciega a:* la rama ``company_currency_id`` de la referencia — nuestro
``AccountMoveLine`` declara ``currency`` y **no** ``company_currency``
(medido: ``grep -n "currency" account_move_line.py`` da un solo campo). Un
apunte en la moneda de la empresa que **no** repite la divisa en ``currency``
no lo ve este guard.

Se porta igual porque un guard parcial bloquea un superconjunto de nada, y
porque la alternativa —no portarlo— deja el cambio destructivo sin ninguna
barrera. Lo que no se hace es presentarlo como completo: cuando entre el
multi-divisa (tarea #114, :ref:`h-api-324`) hay que volver aquí y añadir la
segunda rama.
"""
import fields
from addons.account.models.account_move_line import AccountMoveLine
from addons.base.models.res_company import ResCompany
from addons.base.models.res_currency import ResCurrency
from exceptions import UserError
from orm.environments import execute_query, get_current_company
from tools import date_utils
from tools.sql import SQL
from tools.translate import _


def _has_accounting_entries(self):
    """≙ ``_has_accounting_entries`` (``odoo19c: res_currency.py:34-39``).

    ``True`` si esta divisa ya se usó para redondear algún apunte. Ver la
    ceguera declarada en el docstring del módulo.
    """
    return AccountMoveLine.objects.filter(currency=self).exists()


def assert_rounding_can_change(self, nuevo_rounding):
    """≙ el guard de ``write`` (``odoo19c: res_currency.py:27-32``).

    La referencia lo pone dentro de ``write``; aquí es un método explícito
    porque este ORM no tiene un ``write`` que reciba el ``vals`` completo
    antes de tocar la fila. Se invoca desde el serializer o el servicio que
    cambia el redondeo.

    Bloquea **reducir** la precisión (``nuevo > actual``, en la aritmética de
    la referencia: un ``rounding`` mayor significa menos decimales) y
    ``0``, que la referencia trata como caso especial.
    """
    if (nuevo_rounding > self.rounding or nuevo_rounding == 0) \
            and _has_accounting_entries(self):
        raise UserError(_(
            'No se puede reducir el número de decimales de una divisa que ya '
            'se usó para generar apuntes contables.'))


# === La tabla de divisas del reporte ========================================
# ≙ ``odoo19c: addons/account/models/res_currency.py:42-283``. Ocho métodos
# que construyen la tabla temporal con la que un reporte multi-empresa
# convierte importes a la moneda de la empresa activa.
#
# TRES ADAPTACIONES DE MECANISMO, las tres declaradas:
#
# 1. ``self`` -> ``cls``. La fuente los declara sobre un recordset vacío
#    (``env['res.currency']._get_simple_currency_table(...)``); aquí no hay
#    recordset vacío, así que son ``classmethod`` — el precedente es
#    ``ResCurrency._get_rates`` (``src/addons/base/models/res_currency.py:368``),
#    que hizo la misma conversión. El resto de la firma es literal.
# 2. ``companies`` es un **iterable de ``ResCompany``**, no un recordset, así
#    que ``.filtered`` / la resta de recordsets / ``.mapped`` se escriben como
#    comprensiones. ``.ids`` se vuelve una lista de PK.
# 3. ``IN %(other_company_ids)s`` con tupla -> ``= ANY(%(...)s)`` con LISTA.
#    psycopg3 adapta una tupla como **literal de registro** (``'(1,2)'``), lo
#    que da ``syntax error`` — medido, :ref:`h-api-907`. ``= ANY(array)`` es
#    la forma equivalente que sí acepta una lista de Python.
#
# ``self.env.company`` se resuelve con ``get_current_company()``, que devuelve
# la **PK**, y ``self.env.cr.execute`` con ``execute_query`` — las dos piezas
# que ``orm/environments.py`` declara como el equivalente del ``Environment``.


def _get_simple_currency_table(cls, companies):
    """≙ ``_get_simple_currency_table`` (``odoo19c: res_currency.py:42-50``).

    Crea la tabla de divisas y devuelve su definición para el caso básico de
    un reporte que convierte con las tasas actuales, en un solo periodo.
    """
    if cls._check_currency_table_monocurrency(companies):
        return cls._get_monocurrency_currency_table_sql(companies)

    cls._create_currency_table(
        companies, [('period', None, fields.Date.today())])
    return SQL('account_currency_table')


def _check_currency_table_monocurrency(cls, companies):
    """≙ ``_check_currency_table_monocurrency`` (``:52-58``).

    Si los datos de estas empresas se pueden mostrar con una tabla de una sola
    divisa, basta con ``_get_monocurrency_currency_table_sql``; si no, hace
    falta la tabla temporal completa de ``_create_currency_table``.

    La fuente escribe ``len(companies.currency_id) == 1`` — un recordset
    deduplica al mapear. Aquí se lee la **PK** del descriptor de la FK, que no
    dispara consulta; ``c.currency`` cargaría el objeto por empresa.

    *Métrica:* cardinalidad del conjunto de PK de divisa.
    *Ciega a:* nada respecto de la deduplicación — medido, un conjunto de
    instancias deduplica igual, porque ``Model.__hash__`` es ``hash(self.pk)``.
    Lo que cambia entre las dos formas es el número de consultas, no el
    resultado; por eso el caso que lo cubre mide consultas y no cardinalidad.
    """
    return len({c.currency_id for c in companies}) == 1


def _get_monocurrency_currency_table_sql(cls, companies, use_cta_rates=False):
    """≙ ``_get_monocurrency_currency_table_sql`` (``:60-72``).

    Tabla simplificada, más rápida de generar, para cuando todo lo que hay que
    convertir está en la misma divisa; son unos ``VALUES`` para un JOIN, sin
    tabla temporal.

    Todas las tasas valen 1 —todo está en la misma divisa—, y eso es lo útil:
    la consulta se escribe igual en el caso mono y en el multi.
    """
    unit_rates = [
        SQL("(%(company_id)s, CAST(NULL AS VARCHAR), CAST(NULL AS DATE), "
            "CAST(NULL AS DATE), %(rate_type)s, 1)",
            company_id=company.pk, rate_type=rate_type)
        for company in companies
        for rate_type in (('historical', 'current', 'average')
                          if use_cta_rates else ('current',))
    ]
    return SQL(
        '(VALUES %s) AS account_currency_table'
        '(company_id, period_key, date_from, date_next, rate_type, rate)',
        SQL(',').join(unit_rates))


def _create_currency_table(cls, companies, date_periods, use_cta_rates=False):
    """≙ ``_create_currency_table`` (``:74-140``).

    Crea la tabla temporal con las tasas que permiten agregar importes de
    empresas con distinta moneda funcional en una consulta de reporte. Las
    tasas se calculan desde los ``res.currency.rate`` de la empresa activa.

    Columnas de la tabla:

    - ``company_id`` — la empresa cuyos importes convierte esta tasa.
    - ``period_key`` — el periodo para el que la tasa vale.
    - ``date_from`` — sólo en ``historical``: desde cuándo aplica.
    - ``date_next`` — sólo en ``historical``: la fecha de la tasa siguiente,
      así que ésta aplica hasta el día anterior.
    - ``rate_type`` — ``historical`` convierte cada operación a la fecha en
      que se hizo; ``current`` es la más reciente del periodo, única por
      ``(company_id, period_key)``; ``average`` es el promedio del periodo,
      también única por ese par.
    - ``rate`` — el factor decimal a aplicar directamente al valor, siempre
      que esté en la moneda funcional de ``company_id``.

    :param companies: las empresas para las que generar tasas.
    :param date_periods: tuplas ``(period_key, date_from, date_to)``;
        ``date_from`` puede ser ``None`` para considerar desde el principio.
    :param use_cta_rates: con ``True`` calcula ``current``, ``average`` e
        ``historical`` para todas las empresas y periodos; con ``False``, sólo
        ``current``.
    """
    main_company = ResCompany.objects.get(pk=get_current_company())
    domestic_currency_companies = [
        c for c in companies if c.currency_id == main_company.currency_id]
    domestic_pks = {c.pk for c in domestic_currency_companies}
    other_companies = [c for c in companies if c.pk not in domestic_pks]

    table_builders = []
    if domestic_currency_companies:
        table_builders += [cls._get_table_builder_domestic_currency(
            domestic_currency_companies, use_cta_rates)]

    last_date_to = None
    for period_key, date_from, date_to in date_periods:
        main_company_unit_factor = cls._get_rates(
            [main_company.currency], main_company, date_to,
        )[main_company.currency_id]

        table_builders.append(cls._get_table_builder_current(
            period_key, main_company, other_companies, date_to,
            main_company_unit_factor))

        if use_cta_rates:
            table_builders += [
                cls._get_table_builder_historical(
                    main_company, other_companies, date_to,
                    main_company_unit_factor, last_date_to),
                cls._get_table_builder_average(
                    period_key, main_company, other_companies, date_from,
                    date_to, main_company_unit_factor),
            ]

        last_date_to = date_to

    execute_query(SQL(
        """
            -- Tests may call this function multiple times within the same transaction; we then need to delete an regenerate the currency table
            DROP TABLE IF EXISTS account_currency_table;

            -- Create a temporary table
            CREATE TEMPORARY TABLE
            account_currency_table (company_id, period_key, date_from, date_next, rate_type, rate)
            ON COMMIT DROP
            AS (%(currency_table_build_query)s);

            -- Create a supporting index to avoid seq.scans
            CREATE INDEX account_currency_table_index ON account_currency_table (company_id, rate_type, date_from, date_next);
            -- Update statistics for correct planning
            ANALYZE account_currency_table;
        """,
        currency_table_build_query=SQL(" UNION ALL ").join(
            SQL('(%s)', builder) for builder in table_builders),
    ))


def _get_table_builder_domestic_currency(cls, companies, use_cta_rates):
    """≙ ``_get_table_builder_domestic_currency`` (``:142-164``).

    Una tasa de cada tipo, igual a 1, por empresa. Estas empresas son las que
    comparten divisa con la empresa activa.
    """
    rate_values = []
    for company in companies:
        rate_values.append(SQL(
            "(%s, CAST(NULL AS VARCHAR), CAST(NULL AS DATE), "
            "CAST(NULL AS DATE), 'current', 1)", company.pk))

        if use_cta_rates:
            rate_values += [
                SQL("(%s, CAST(NULL AS VARCHAR), CAST(NULL AS DATE), "
                    "CAST(NULL AS DATE), 'average', 1)", company.pk),
                SQL("(%s, CAST(NULL AS VARCHAR), CAST(NULL AS DATE), "
                    "CAST(NULL AS DATE), 'historical', 1)", company.pk),
            ]

    return SQL(
        """
            SELECT *
            FROM ( VALUES
                %(rate_values)s
            ) values
        """,
        rate_values=SQL(", ").join(rate_values),
    )


def _get_table_builder_current(cls, period_key, main_company, other_companies,
                               date_to, main_company_unit_factor):
    """≙ ``_get_table_builder_current`` (``:166-190``)."""
    return SQL(
        """
            SELECT DISTINCT ON (other_company.id)
                other_company.id,
                %(period_key)s,
                CAST(NULL AS DATE),
                CAST(NULL AS DATE),
                'current',
                CASE WHEN rate.id IS NOT NULL THEN %(main_company_unit_factor)s / rate.rate ELSE 1 END
            FROM res_company other_company
            LEFT JOIN res_currency_rate rate
                ON rate.currency_id = other_company.currency_id
                AND rate.name <= %(date_to)s
                AND rate.company_id = %(main_company_id)s
            WHERE
                other_company.id = ANY(%(other_company_ids)s)
            ORDER BY other_company.id, rate.name DESC
        """,
        period_key=period_key,
        main_company_id=main_company.root_id.pk,
        other_company_ids=[c.pk for c in other_companies],
        date_to=date_to,
        main_company_unit_factor=main_company_unit_factor,
    )


def _get_table_builder_historical(cls, main_company, other_companies, date_to,
                                  main_company_unit_factor, date_exclude):
    """≙ ``_get_table_builder_historical`` (``:192-216``)."""
    return SQL(
        """
            SELECT
                other_company.id,
                CAST(NULL AS VARCHAR),
                rate.name,
                LAG(rate.name, 1) OVER (PARTITION BY other_company.id, rate.currency_id ORDER BY rate.name DESC),
                'historical',
                %(main_company_unit_factor)s / rate.rate
            FROM res_company other_company
            JOIN res_currency_rate rate
                ON rate.currency_id = other_company.currency_id
            WHERE
                other_company.id = ANY(%(other_company_ids)s)
                AND rate.company_id = %(main_company_id)s
                AND rate.name <= %(date_to)s
                %(exclusion_condition)s
        """,
        main_company_id=main_company.root_id.pk,
        other_company_ids=[c.pk for c in other_companies],
        main_company_unit_factor=main_company_unit_factor,
        date_to=date_to,
        exclusion_condition=(
            SQL("AND rate.name > %(date_exclude)s", date_exclude=date_exclude)
            if date_exclude else SQL()),
    )


def _get_table_builder_average(cls, period_key, main_company, other_companies,
                               date_from, date_to, main_company_unit_factor):
    """≙ ``_get_table_builder_average`` (``:218-283``)."""
    if not date_from:
        # When there is no start date, we want to compute the average rate on the current year only
        date_from = date_utils.start_of(fields.Date.from_string(date_to), 'year')

    return SQL(
        """
            SELECT
                rate_with_days.other_company_id,
                %(period_key)s,
                CAST(NULL AS DATE),
                CAST(NULL AS DATE),
                'average',
                SUM(%(main_company_unit_factor)s / rate_with_days.rate * rate_with_days.number_of_days) / SUM(rate_with_days.number_of_days)
            FROM (
                SELECT
                    other_company.id as other_company_id,
                    rate.rate AS rate,
                    EXTRACT (
                        'Day' FROM COALESCE(
                            LEAD(rate.name, 1) OVER (PARTITION BY other_company.id, rate.currency_id ORDER BY rate.name ASC)::TIMESTAMP,
                            %(date_to)s::TIMESTAMP + INTERVAL '1' DAY
                        ) - rate.name::TIMESTAMP
                    ) AS number_of_days
                FROM res_company other_company
                JOIN res_currency_rate rate
                    ON rate.currency_id = other_company.currency_id
                WHERE
                rate.name <= %(date_to)s
                AND rate.name >= %(date_from)s
                AND other_company.id = ANY(%(other_company_ids)s)
                AND rate.company_id = %(main_company_id)s

                UNION ALL

                (
                    SELECT DISTINCT ON (other_company.id)
                        other_company.id as other_company_id,
                        COALESCE(out_period_rate.rate, 1.0) AS rate,
                        EXTRACT('Day' FROM COALESCE(in_period_rate.name::TIMESTAMP, %(date_to)s::TIMESTAMP + INTERVAL '1' DAY) - %(date_from)s::TIMESTAMP) AS number_of_days

                    FROM res_company other_company

                    LEFT JOIN res_currency_rate in_period_rate
                        ON in_period_rate.currency_id = other_company.currency_id
                        AND in_period_rate.name <= %(date_to)s
                        AND in_period_rate.name >= %(date_from)s
                        AND in_period_rate.company_id = %(main_company_id)s

                    LEFT JOIN res_currency_rate out_period_rate
                        ON out_period_rate.currency_id = other_company.currency_id
                        AND out_period_rate.company_id = %(main_company_id)s
                        AND out_period_rate.name < %(date_from)s

                    WHERE
                    other_company.id = ANY(%(other_company_ids)s)
                    ORDER BY other_company.id, in_period_rate.name ASC, out_period_rate.name DESC
                )
            ) rate_with_days
            GROUP BY rate_with_days.other_company_id
        """,
        period_key=period_key,
        main_company_id=main_company.root_id.pk,
        other_company_ids=[c.pk for c in other_companies],
        date_from=date_from,
        date_to=date_to,
        main_company_unit_factor=main_company_unit_factor,
    )


def apply_account_extensions():
    """Cuelga el guard de la divisa — ≙ ``_inherit``.

    Se invoca desde ``AccountConfig.ready()``. No añade columnas: los dos
    campos de la referencia están bloqueados (ver el docstring del módulo).
    """
    for nombre, funcion in (
        ('_has_accounting_entries', _has_accounting_entries),
        ('assert_rounding_can_change', assert_rounding_can_change),
    ):
        if not hasattr(ResCurrency, nombre):
            setattr(ResCurrency, nombre, funcion)

    # Los ocho de la tabla de divisas van como ``classmethod``: la fuente los
    # invoca sobre un recordset vacío y aquí el receptor es el modelo, igual
    # que ``ResCurrency._get_rates``.
    for nombre, funcion in (
        ('_get_simple_currency_table', _get_simple_currency_table),
        ('_check_currency_table_monocurrency', _check_currency_table_monocurrency),
        ('_get_monocurrency_currency_table_sql', _get_monocurrency_currency_table_sql),
        ('_create_currency_table', _create_currency_table),
        ('_get_table_builder_domestic_currency', _get_table_builder_domestic_currency),
        ('_get_table_builder_current', _get_table_builder_current),
        ('_get_table_builder_historical', _get_table_builder_historical),
        ('_get_table_builder_average', _get_table_builder_average),
    ):
        if not hasattr(ResCurrency, nombre):
            setattr(ResCurrency, nombre, classmethod(funcion))
