# -*- coding: utf-8 -*-
r"""``AccountMoveLine`` — el mapeo apunte-de-impuesto ↔ apunte-de-base (SQL crudo).

Adaptación de ``addons/account/models/account_move_line_tax_details.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, 512 líneas, LGPL-3 — atribución y
aviso de licencia preservados, DEC-KX-03). Tres símbolos, los tres
transcritos con su forma SQL completa.

Bloqueado por columnas concretas ausentes en ``AccountMoveLine`` — medido
============================================================================

El puerto de ``AccountMoveLine`` en este árbol
(``addons/account/models/account_move_line.py``, 116 líneas) es un recorte
deliberado: ``move``, ``account``, ``name``, ``debit``, ``credit``,
``balance``, ``display_type``, ``quantity``, ``price_unit``, ``currency``,
``full_reconcile``, ``matching_number``. La consulta de la referencia lee,
además, columnas que **no existen** en ese modelo — medido con
``grep -n "tax_line_id\|tax_repartition_line_id\|group_tax_id\|partner_id\|
company_currency_id\|amount_currency\|analytic_distribution"
account_move_line.py`` → **0 hits** para las siete.

Este archivo transcribe la SQL **completa y fiel** (la forma, tal como
``porte-completo-no-parcial.md`` exige incluso para lo bloqueado — mismo
criterio que ``res_partner_bank.py::_get_qr_code_base64``): las tablas
(``account_move_line``, ``account_move``, ``account_tax``,
``account_tax_repartition_line``, ``res_currency``) SÍ existen con esos
nombres exactos en este árbil (verificado: ``grep -n db_table``, ver el
comando en la sección de verificación). Lo que falta son columnas dentro de
``account_move_line`` y la tabla puente
``account_move_line_account_tax_rel`` (el M2M ``tax_ids``, tampoco portado).

Ejecutar esta SQL hoy falla en Postgres con ``UndefinedColumn`` en la
primera columna ausente que toque — no es un fallo silencioso, es un fallo
ruidoso y localizable. Sucesor: portar las siete columnas + el M2M sobre
``AccountMoveLine`` (fuera del alcance de este porte — no está en la lista
de archivos a escribir) y entonces esta consulta queda operable sin tocar
este archivo.

``Query.from_clause``/``where_clause`` de Odoo → sin equivalente aquí
==========================================================================

``_get_query_tax_details_from_domain`` recibe, en la referencia, un dominio
ORM y lo resuelve a través de ``self.env['account.move.line']._search(domain)``,
que expone ``.from_clause``/``.where_clause`` como fragmentos SQL
independientes — el objeto ``Query`` interno de Odoo
(``odoo19c: odoo/orm/query.py``). Django expone ``QuerySet.query`` pero sólo
compila a un ``SELECT`` completo (medido: ``grep -rn "from_clause\|where_clause"
src/orm/`` → 0 hits; no hay fraccionador). **Divergencia de mecanismo,
adaptada, no bloqueada del todo**: se acepta un ``QuerySet`` de
``AccountMoveLine`` ya filtrado y se envuelve como subconsulta con el alias
``account_move_line`` — el resto de la SQL referencia esa tabla por nombre
literal y una subconsulta con el mismo alias resuelve igual en PostgreSQL.
``search_condition`` queda ``SQL('TRUE')`` porque el filtro ya se aplicó
dentro de la subconsulta.
"""
from tools.sql import SQL

from addons.account.models.account_move_line import AccountMoveLine
from addons.account.models.account_tax import AccountTax
from orm.method_chain import chain_method


def _get_query_tax_details_from_domain(cls, queryset, fallback=True):
    """≙ ``_get_query_tax_details_from_domain`` (``odoo19c:
    account_move_line_tax_details.py:11-20``).

    :param queryset: un ``QuerySet`` de ``AccountMoveLine`` ya filtrado —
        sustituye al dominio ORM de la referencia (ver "``Query.from_clause``
        /``where_clause``..." en el docstring del módulo).
    :param fallback: igual que la referencia.
    :return: objeto ``SQL``.
    """
    compiled_sql, compiled_params = queryset.query.sql_with_params()
    subquery = SQL(compiled_sql, *compiled_params)
    table_references = SQL(
        '(%(subquery)s) AS account_move_line', subquery=subquery)
    search_condition = SQL('TRUE')
    return _get_query_tax_details(cls, table_references, search_condition, fallback=fallback)


def _get_extra_query_base_tax_line_mapping(cls):
    """≙ ``_get_extra_query_base_tax_line_mapping`` (``odoo19c:
    account_move_line_tax_details.py:22-25``, terminal — sobreescribir)."""
    return SQL()


def _get_query_tax_details(cls, table_references, search_condition, fallback=True):
    """≙ ``_get_query_tax_details`` (``odoo19c:
    account_move_line_tax_details.py:27-512``).

    **Bloqueado por columnas ausentes en ``AccountMoveLine``** — ver el
    docstring del módulo. La SQL de abajo es una transcripción fiel de la
    referencia (mismas tablas, mismas columnas, mismo orden de CTEs); las
    columnas que ``AccountMoveLine`` de este árbol no declara todavía
    (``tax_line_id``, ``tax_repartition_line_id``, ``group_tax_id``,
    ``partner_id``, ``company_currency_id``, ``amount_currency``,
    ``analytic_distribution``) harán que PostgreSQL levante
    ``UndefinedColumn`` al ejecutarla — ruidoso, no silencioso.
    """
    group_taxes = cls.env_tax_model().objects.filter(amount_type='group')

    group_taxes_query_list = []
    for group_tax in group_taxes:
        children_taxes = list(group_tax.children_tax_ids.all())
        if not children_taxes:
            continue
        children_ids = [t.pk for t in children_taxes]
        children_taxes_in_query = SQL(
            ','.join('%s' for _dummy in children_ids), *children_ids)
        group_taxes_query_list.append(SQL(
            'WHEN tax.id = %s THEN ARRAY[%s]', group_tax.pk, children_taxes_in_query))

    if group_taxes_query_list:
        group_taxes_query = SQL(
            '''UNNEST(CASE %s ELSE ARRAY[tax.id] END)''',
            SQL(' ').join(group_taxes_query_list))
    else:
        group_taxes_query = SQL('tax.id')

    if fallback:
        fallback_query = SQL(
            '''
            UNION ALL

            SELECT
                account_move_line.id AS tax_line_id,
                base_line.id AS base_line_id,
                base_line.id AS src_line_id,
                base_line.balance AS base_amount,
                base_line.amount_currency AS base_amount_currency
            FROM %(table_references)s
            LEFT JOIN base_tax_line_mapping ON
                base_tax_line_mapping.tax_line_id = account_move_line.id
            JOIN account_move_line_account_tax_rel tax_rel ON
                tax_rel.account_tax_id = COALESCE(account_move_line.group_tax_id, account_move_line.tax_line_id)
            JOIN account_move_line base_line ON
                base_line.id = tax_rel.account_move_line_id
                AND base_line.tax_repartition_line_id IS NULL
                AND base_line.move_id = account_move_line.move_id
                AND base_line.currency_id = account_move_line.currency_id
            WHERE base_tax_line_mapping.tax_line_id IS NULL
            AND %(search_condition)s
            ''',
            table_references=table_references,
            search_condition=search_condition,
        )
    else:
        fallback_query = SQL()

    extra_query_base_tax_line_mapping = cls._get_extra_query_base_tax_line_mapping()

    return SQL(
        '''
        WITH base_tax_line_mapping AS (

            SELECT
                account_move_line.id AS tax_line_id,
                base_line.id AS base_line_id,
                base_line.balance AS base_amount,
                base_line.amount_currency AS base_amount_currency

            FROM %(table_references)s
            JOIN account_tax_repartition_line tax_rep ON
                tax_rep.id = account_move_line.tax_repartition_line_id
            JOIN account_tax tax ON
                tax.id = account_move_line.tax_line_id
            JOIN account_move_line_account_tax_rel tax_rel ON
                tax_rel.account_tax_id = COALESCE(account_move_line.group_tax_id, account_move_line.tax_line_id)
            JOIN account_move move ON
                move.id = account_move_line.move_id
            JOIN account_move_line base_line ON
                base_line.id = tax_rel.account_move_line_id
                AND base_line.tax_repartition_line_id IS NULL
                AND base_line.move_id = account_move_line.move_id
                AND (
                    move.move_type != 'entry'
                    OR (tax.tax_exigibility = 'on_payment' AND tax.cash_basis_transition_account_id IS NOT NULL)
                    OR sign(account_move_line.balance) = sign(base_line.balance * tax.amount * tax_rep.factor_percent)
                )
                AND COALESCE(base_line.partner_id, 0) = COALESCE(account_move_line.partner_id, 0)
                AND base_line.currency_id = account_move_line.currency_id
                AND (
                    COALESCE(tax_rep.account_id, base_line.account_id) = account_move_line.account_id
                    OR (tax.tax_exigibility = 'on_payment' AND tax.cash_basis_transition_account_id IS NOT NULL)
                )
                AND (
                    (tax.analytic IS NOT TRUE AND tax_rep.use_in_tax_closing IS TRUE)
                    OR (base_line.analytic_distribution IS NULL AND account_move_line.analytic_distribution IS NULL)
                    OR base_line.analytic_distribution = account_move_line.analytic_distribution
                )
                %(extra_query_base_tax_line_mapping)s
            JOIN res_currency curr ON
                curr.id = account_move_line.currency_id
            JOIN res_currency comp_curr ON
                comp_curr.id = account_move_line.company_currency_id
            LEFT JOIN LATERAL (
                SELECT ARRAY_AGG(sub.tax_id ORDER BY sub.sequence, sub.tax_id) AS tax_ids
                FROM (
                    SELECT
                        %(group_taxes_query)s AS tax_id,
                        tax.sequence
                    FROM account_move_line_account_tax_rel tax_rel
                    JOIN account_tax tax ON tax.id = tax_rel.account_tax_id
                    WHERE tax.is_base_affected
                    AND tax_rel.account_move_line_id = account_move_line.id
                ) AS sub
            ) tax_line_tax_ids ON TRUE
            LEFT JOIN LATERAL (
                SELECT ARRAY_AGG(sub.tax_id ORDER BY sub.sequence, sub.tax_id) AS tax_ids
                FROM (
                    SELECT
                        %(group_taxes_query)s AS tax_id,
                        tax.sequence
                    FROM account_move_line_account_tax_rel tax_rel
                    JOIN account_tax tax ON tax.id = tax_rel.account_tax_id
                    WHERE tax.is_base_affected
                    AND tax_rel.account_move_line_id = base_line.id
                ) AS sub
            ) base_line_tax_ids ON TRUE
            WHERE account_move_line.tax_repartition_line_id IS NOT NULL
                AND %(search_condition)s
                AND (
                    NOT tax.include_base_amount
                    OR base_line_tax_ids.tax_ids[ARRAY_LENGTH(base_line_tax_ids.tax_ids, 1) - COALESCE(ARRAY_LENGTH(tax_line_tax_ids.tax_ids, 1), 0):ARRAY_LENGTH(base_line_tax_ids.tax_ids, 1)]
                        = ARRAY[account_move_line.tax_line_id] || COALESCE(tax_line_tax_ids.tax_ids, ARRAY[]::INTEGER[])
                )
        ),


        tax_amount_affecting_base_to_dispatch AS (

            SELECT
                tax_line.id AS tax_line_id,
                base_line.id AS base_line_id,
                account_move_line.id AS src_line_id,

                tax_line.company_id,
                comp_curr.id AS company_currency_id,
                comp_curr.decimal_places AS comp_curr_prec,
                curr.id AS currency_id,
                curr.decimal_places AS curr_prec,

                tax_line.tax_line_id AS tax_id,

                base_line.balance AS base_amount,
                SUM(
                    CASE WHEN tax.amount_type = 'fixed'
                    THEN CASE WHEN base_line.balance < 0 THEN -1 ELSE 1 END * ABS(COALESCE(base_line.quantity, 1.0))
                    ELSE base_line.balance
                    END
                ) OVER (PARTITION BY tax_line.id, account_move_line.id ORDER BY tax_line.tax_line_id, base_line.id) AS cumulated_base_amount,
                SUM(
                    CASE WHEN tax.amount_type = 'fixed'
                    THEN CASE WHEN base_line.balance < 0 THEN -1 ELSE 1 END * ABS(COALESCE(base_line.quantity, 1.0))
                    ELSE base_line.balance
                    END
                ) OVER (PARTITION BY tax_line.id, account_move_line.id) AS total_base_amount,
                account_move_line.balance AS total_tax_amount,

                base_line.amount_currency AS base_amount_currency,
                SUM(
                    CASE WHEN tax.amount_type = 'fixed'
                    THEN CASE WHEN base_line.amount_currency < 0 THEN -1 ELSE 1 END * ABS(COALESCE(base_line.quantity, 1.0))
                    ELSE base_line.amount_currency
                    END
                ) OVER (PARTITION BY tax_line.id, account_move_line.id ORDER BY tax_line.tax_line_id, base_line.id) AS cumulated_base_amount_currency,
                SUM(
                    CASE WHEN tax.amount_type = 'fixed'
                    THEN CASE WHEN base_line.amount_currency < 0 THEN -1 ELSE 1 END * ABS(COALESCE(base_line.quantity, 1.0))
                    ELSE base_line.amount_currency
                    END
                ) OVER (PARTITION BY tax_line.id, account_move_line.id) AS total_base_amount_currency,
                account_move_line.amount_currency AS total_tax_amount_currency

            FROM %(table_references)s
            JOIN account_tax tax_include_base_amount ON
                tax_include_base_amount.include_base_amount
                AND tax_include_base_amount.id = account_move_line.tax_line_id
            JOIN base_tax_line_mapping base_tax_line_mapping ON
                base_tax_line_mapping.tax_line_id = account_move_line.id
            JOIN account_move_line_account_tax_rel tax_rel ON
                tax_rel.account_move_line_id = base_tax_line_mapping.tax_line_id
            JOIN account_tax tax ON
                tax.id = tax_rel.account_tax_id
            JOIN base_tax_line_mapping tax_line_matching ON
                tax_line_matching.base_line_id = base_tax_line_mapping.base_line_id
            JOIN account_move_line tax_line ON
                tax_line.id = tax_line_matching.tax_line_id
                AND tax_line.tax_line_id = tax_rel.account_tax_id
            JOIN res_currency curr ON
                curr.id = tax_line.currency_id
            JOIN res_currency comp_curr ON
                comp_curr.id = tax_line.company_currency_id
            JOIN account_move_line base_line ON
                base_line.id = base_tax_line_mapping.base_line_id
            WHERE %(search_condition)s
        ),


        base_tax_matching_base_amounts AS (

            SELECT
                tax_line_id,
                base_line_id,
                base_line_id AS src_line_id,
                base_amount,
                base_amount_currency
            FROM base_tax_line_mapping

            UNION ALL

            SELECT
                sub.tax_line_id,
                sub.base_line_id,
                sub.src_line_id,

                ROUND(
                    COALESCE(SIGN(sub.cumulated_base_amount) * sub.total_tax_amount * ABS(sub.cumulated_base_amount) / NULLIF(sub.total_base_amount, 0.0), 0.0),
                    sub.comp_curr_prec
                )
                - LAG(ROUND(
                    COALESCE(SIGN(sub.cumulated_base_amount) * sub.total_tax_amount * ABS(sub.cumulated_base_amount) / NULLIF(sub.total_base_amount, 0.0), 0.0),
                    sub.comp_curr_prec
                ), 1, 0.0)
                OVER (
                    PARTITION BY sub.tax_line_id, sub.src_line_id ORDER BY sub.tax_id, sub.base_line_id
                ) AS base_amount,

                ROUND(
                    COALESCE(SIGN(sub.cumulated_base_amount_currency) * sub.total_tax_amount_currency * ABS(sub.cumulated_base_amount_currency) / NULLIF(sub.total_base_amount_currency, 0.0), 0.0),
                    sub.curr_prec
                )
                - LAG(ROUND(
                    COALESCE(SIGN(sub.cumulated_base_amount_currency) * sub.total_tax_amount_currency * ABS(sub.cumulated_base_amount_currency) / NULLIF(sub.total_base_amount_currency, 0.0), 0.0),
                    sub.curr_prec
                ), 1, 0.0)
                OVER (
                    PARTITION BY sub.tax_line_id, sub.src_line_id ORDER BY sub.tax_id, sub.base_line_id
                ) AS base_amount_currency
            FROM tax_amount_affecting_base_to_dispatch sub
            JOIN account_move_line tax_line ON
                tax_line.id = sub.tax_line_id

            %(fallback_query)s
        ),


        base_tax_matching_all_amounts AS (

            SELECT
                sub.tax_line_id,
                sub.base_line_id,
                sub.src_line_id,

                tax_line.tax_line_id AS tax_id,
                tax_line.group_tax_id,
                tax_line.tax_repartition_line_id,

                tax_line.company_id,
                tax_line.display_type AS display_type,
                comp_curr.id AS company_currency_id,
                comp_curr.decimal_places AS comp_curr_prec,
                curr.id AS currency_id,
                curr.decimal_places AS curr_prec,
                (
                    tax.tax_exigibility != 'on_payment'
                    OR tax_move.tax_cash_basis_rec_id IS NOT NULL
                    OR tax_move.always_tax_exigible
                ) AS tax_exigible,
                base_line.account_id AS base_account_id,

                sub.base_amount,
                SUM(
                    CASE WHEN tax.amount_type = 'fixed'
                    THEN CASE WHEN base_line.balance < 0 THEN -1 ELSE 1 END * ABS(COALESCE(base_line.quantity, 1.0))
                    ELSE sub.base_amount
                    END
                ) OVER (PARTITION BY tax_line.id ORDER BY tax_line.tax_line_id, sub.base_line_id, sub.src_line_id) AS cumulated_base_amount,
                SUM(
                    CASE WHEN tax.amount_type = 'fixed'
                    THEN CASE WHEN base_line.balance < 0 THEN -1 ELSE 1 END * ABS(COALESCE(base_line.quantity, 1.0))
                    ELSE sub.base_amount
                    END
                ) OVER (PARTITION BY tax_line.id) AS total_base_amount,
                tax_line.balance AS total_tax_amount,

                sub.base_amount_currency,
                SUM(
                    CASE WHEN tax.amount_type = 'fixed'
                    THEN CASE WHEN base_line.amount_currency < 0 THEN -1 ELSE 1 END * ABS(COALESCE(base_line.quantity, 1.0))
                    ELSE sub.base_amount_currency
                    END
                ) OVER (PARTITION BY tax_line.id ORDER BY tax_line.tax_line_id, sub.base_line_id, sub.src_line_id) AS cumulated_base_amount_currency,
                SUM(
                    CASE WHEN tax.amount_type = 'fixed'
                    THEN CASE WHEN base_line.amount_currency < 0 THEN -1 ELSE 1 END * ABS(COALESCE(base_line.quantity, 1.0))
                    ELSE sub.base_amount_currency
                    END
                ) OVER (PARTITION BY tax_line.id) AS total_base_amount_currency,
                tax_line.amount_currency AS total_tax_amount_currency

            FROM base_tax_matching_base_amounts sub
            JOIN account_move_line tax_line ON
                tax_line.id = sub.tax_line_id
            JOIN account_move tax_move ON
                tax_move.id = tax_line.move_id
            JOIN account_move_line base_line ON
                base_line.id = sub.base_line_id
            JOIN account_tax tax ON
                tax.id = tax_line.tax_line_id
            JOIN res_currency curr ON
                curr.id = tax_line.currency_id
            JOIN res_currency comp_curr ON
                comp_curr.id = tax_line.company_currency_id

        )


        SELECT
            sub.tax_line_id || '-' || sub.base_line_id || '-' || sub.src_line_id AS id,

            sub.base_line_id,
            sub.tax_line_id,
            sub.display_type,
            sub.src_line_id,

            sub.tax_id,
            sub.group_tax_id,
            sub.tax_exigible,
            sub.base_account_id,
            sub.tax_repartition_line_id,

            sub.base_amount,
            COALESCE(
                ROUND(
                    COALESCE(SIGN(sub.cumulated_base_amount) * sub.total_tax_amount * ABS(sub.cumulated_base_amount) / NULLIF(sub.total_base_amount, 0.0), 0.0),
                    sub.comp_curr_prec
                )
                - LAG(ROUND(
                    COALESCE(SIGN(sub.cumulated_base_amount) * sub.total_tax_amount * ABS(sub.cumulated_base_amount) / NULLIF(sub.total_base_amount, 0.0), 0.0),
                    sub.comp_curr_prec
                ), 1, 0.0)
                OVER (
                    PARTITION BY sub.tax_line_id ORDER BY sub.tax_id, sub.base_line_id
                ),
                0.0
            ) AS tax_amount,

            sub.base_amount_currency,
            COALESCE(
                ROUND(
                    COALESCE(SIGN(sub.cumulated_base_amount_currency) * sub.total_tax_amount_currency * ABS(sub.cumulated_base_amount_currency) / NULLIF(sub.total_base_amount_currency, 0.0), 0.0),
                    sub.curr_prec
                )
                - LAG(ROUND(
                    COALESCE(SIGN(sub.cumulated_base_amount_currency) * sub.total_tax_amount_currency * ABS(sub.cumulated_base_amount_currency) / NULLIF(sub.total_base_amount_currency, 0.0), 0.0),
                    sub.curr_prec
                ), 1, 0.0)
                OVER (
                    PARTITION BY sub.tax_line_id ORDER BY sub.tax_id, sub.base_line_id
                ),
                0.0
            ) AS tax_amount_currency
        FROM base_tax_matching_all_amounts sub
        ''',
        extra_query_base_tax_line_mapping=extra_query_base_tax_line_mapping,
        group_taxes_query=group_taxes_query,
        search_condition=search_condition,
        table_references=table_references,
        fallback_query=fallback_query,
    )


def env_tax_model(cls):
    """``self.env['account.tax']`` — la clase ``AccountTax`` de este mismo
    addon (importada al top del módulo: verificado sin ciclo, ``account_tax
    .py`` no importa ``account_move_line.py`` ni transitivamente)."""
    return AccountTax


def apply_account_extensions():
    """Cuelga el mapeo impuesto↔base sobre ``AccountMoveLine`` — extensión
    del MISMO addon (no cross-app).

    **Todavía no cableado** — mismo estado que
    ``account_journal_dashboard.py`` de este mismo pase: ni invocado desde
    ``AccountConfig.ready()`` ni desde el ``__init__.py`` del addon.
    """
    chain_method(AccountMoveLine, '_get_query_tax_details_from_domain',
                 classmethod(_get_query_tax_details_from_domain))
    chain_method(AccountMoveLine, '_get_extra_query_base_tax_line_mapping',
                 classmethod(_get_extra_query_base_tax_line_mapping))
    chain_method(AccountMoveLine, '_get_query_tax_details',
                 classmethod(_get_query_tax_details))
    if not hasattr(AccountMoveLine, 'env_tax_model'):
        AccountMoveLine.env_tax_model = classmethod(env_tax_model)
