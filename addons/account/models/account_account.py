"""``account.account`` — plan de cuentas (Odoo ``account``).

Portación fiel de ``account_account.py`` (Odoo 18/19). Campos persistidos
núcleo: ``code``, ``name``, ``account_type`` (Selection), ``reconcile``,
``deprecated``, ``currency``, ``note``. ``internal_group`` deriva de
``account_type`` (Odoo ``_compute_internal_group``) → se computa en ``save()``.

Cross-app (DEC-SALE-01): ``currency`` → ``base.ResCurrency``; ``company`` →
``base.ResCompany`` (Odoo ``res.company``).

Hallazgo H-ACC-01 (drift 18→19): el enum ``account_type`` de 19 añade
``expense_other`` respecto de 18. Se adopta el **superset de 19** (nada
fabricado; ambos valores existen en 19). Ver audit.
"""

import itertools
from bisect import bisect_left

from django.apps import apps
from django.db.models import Q

import api
import fields
import models
from exceptions import UserError, ValidationError
from orm.environments import company_scope, env
from tools.query import Query
from tools.sql import SQL
from tools.translate import _

from addons.base.models import ResCompany


class AccountAccount(models.BaseModel):
    """``account.account`` — cuenta contable del plan (Odoo base contable)."""

    #: Los atributos de clase de la fuente
    #: (``odoo19c: account_account.py:20-25``). Sin ``_name`` el modelo no
    #: entra en ``orm.registry.MODELS_BY_NAME`` y ``env['account.account']``
    #: no resuelve.
    _name = 'account.account'
    #: ≙ ``_inherit`` (``:21``), verbatim.
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Account'
    #: ≙ ``_order = 'code, placeholder_code'`` (``:23``). ``placeholder_code``
    #: no está portado, así que ``Meta.ordering`` ordena sólo por ``code``.
    _order = 'code, placeholder_code'
    #: ≙ ``_check_company_auto = True`` (``:24``). Sin efecto todavía: esta
    #: clase no hereda ``CheckCompanyMixin`` (es un ``models.Model`` de
    #: Django, no ``TimeStampedModel``), que es quien lo lee al guardar.
    _check_company_auto = True
    #: **Divergencia declarada** de ``_check_company_domain =
    #: models.check_companies_domain_parent_of`` (``:25``). La fuente usa el
    #: plural sobre el M2M ``company_ids``. Desde MC1 ``company_ids`` existe
    #: y ``save`` lo mantiene igual a ``company``, pero los consumidores
    #: todavía filtran por ``company``; el singular
    #: ``check_company_domain_parent_of`` conserva el criterio jerárquico de
    #: la fuente sobre ese campo hasta MC2, que pasa los consumidores a
    #: ``company_ids`` y cambia al plural
    #: (``designs/account-account-multicompany-code.md``).
    _check_company_domain = classmethod(models.check_company_domain_parent_of)

    # account_type — superset de Odoo 19 (18 + expense_other). H-ACC-01.
    ACCOUNT_TYPES = [
        ('asset_receivable', 'Por cobrar'),
        ('asset_cash', 'Banco y efectivo'),
        ('asset_current', 'Activo circulante'),
        ('asset_non_current', 'Activo no circulante'),
        ('asset_prepayments', 'Pagos anticipados'),
        ('asset_fixed', 'Activo fijo'),
        ('liability_payable', 'Por pagar'),
        ('liability_credit_card', 'Tarjeta de crédito'),
        ('liability_current', 'Pasivo circulante'),
        ('liability_non_current', 'Pasivo no circulante'),
        ('equity', 'Capital'),
        ('equity_unaffected', 'Resultado del ejercicio'),
        ('income', 'Ingreso'),
        ('income_other', 'Otros ingresos'),
        ('expense', 'Gasto'),
        ('expense_depreciation', 'Depreciación'),
        ('expense_direct_cost', 'Costo de ventas'),
        ('expense_other', 'Otros gastos'),
        ('off_balance', 'Fuera de balance'),
    ]

    # internal_group — Odoo _compute_internal_group: prefijo del account_type.
    INTERNAL_GROUPS = [
        ('equity', 'Capital'),
        ('asset', 'Activo'),
        ('liability', 'Pasivo'),
        ('income', 'Ingreso'),
        ('expense', 'Gasto'),
        ('off', 'Fuera de balance'),
    ]

    #: ≙ ``code`` (``odoo19c: addons/account/models/account_account.py:39``):
    #: sin columna, calculado sobre ``code_store`` en la raíz de la empresa
    #: activa, con búsqueda e inverso (``:333-353``).
    code = fields.Char(
        compute='_compute_code',
        search='_search_code',
        inverse='_inverse_code',
        store=False,
        help_text='Código de cuenta (Odoo account.account.code).',
    )
    name = fields.Char(
        max_length=255,
        help_text='Nombre de la cuenta (Odoo name, requerido).',
    )
    account_type = fields.Selection(
        max_length=32,
        choices=ACCOUNT_TYPES,
        help_text='Tipo de cuenta (Odoo account_type, requerido).',
        compute='_compute_account_type',
        store=True,
        readonly=False,
        precompute=True,
    )
    #: DIVERGENCIA DECLARADA — la fuente NO le da columna: la declara
    #: ``compute="_compute_internal_group", search="_search_internal_group"``
    #: sin ``store`` (``odoo19c: account_account.py:76-87``), mas el ayudante
    #: ``_get_internal_group`` (``:648-649``).
    #:
    #: Aqui lleva columna desde ``0001_initial`` y **no se puede retirar hoy**.
    #: Medido: el compilador de Django no resuelve un campo sin columna ni en
    #: el modelo directo —``FieldError: Cannot resolve keyword ... into
    #: field``, probado sobre tres campos vivos de ``ResPartner``— y el
    #: consumidor de esta columna atraviesa una FK:
    #: ``digest.py:133`` filtra ``account__internal_group='income'``. Con
    #: ``store=False`` ese filtro deja de compilar.
    #:
    #: El enlace automatico de ``search=`` cubre hoy solo el campo ``related``
    #: (``orm/fields_nonstored.py:521``), no el calculado. Sucesor con su
    #: condicion de cierre: tarea #310.
    internal_group = fields.Selection(
        max_length=16,
        choices=INTERNAL_GROUPS,
        blank=True,
        default='',
        help_text=(
            'Grupo interno derivado de account_type (Odoo internal_group).'
        ),
        compute='_compute_internal_group',
        store=True,
    )
    reconcile = fields.Boolean(
        default=False,
        help_text='Permite conciliación (Odoo reconcile).',
    )
    deprecated = fields.Boolean(
        default=False,
        help_text='Cuenta obsoleta (Odoo deprecated).',
    )
    currency = fields.Many2one(
        'base.ResCurrency',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accounts',
        help_text='Moneda de la cuenta (Odoo currency_id).',
    )
    company = fields.Many2one(
        'base.ResCompany',
        null=False, on_delete=models.CASCADE,
        related_name='accounts',
        help_text='Empresa (Odoo company_id / company_ids).',
    )
    #: ≙ ``company_ids``
    #: (``odoo19c: addons/account/models/account_account.py:97-98``): la
    #: cuenta pertenece a varias empresas. Durante MC1 convive con
    #: ``company``, y ``save`` la mantiene al día
    #: (``designs/account-account-multicompany-code.md``).
    company_ids = fields.Many2many(
        'base.ResCompany',
        blank=True,
        related_name='+',
        db_table='account_account_res_company_rel',
        help_text='Empresas de la cuenta (Odoo company_ids).',
    )
    #: ≙ ``code_store = fields.Char(company_dependent=True)`` (``:40``): el
    #: código por empresa raíz, del que la fuente calcula ``code``. Durante
    #: MC1 ``save`` lo escribe desde la columna ``code``.
    code_store = fields.Char(
        company_dependent=True,
        help_text='Código por empresa raíz (Odoo code_store).',
    )
    #: ≙ ``placeholder_code``
    #: (``odoo19c: addons/account/models/account_account.py:41``): el
    #: código en la empresa activa, o el de la primera empresa autorizada con
    #: su nombre. Sin columna; ordena por la expresión de ``_field_to_sql``,
    #: que es lo que hace válido ``_order``.
    placeholder_code = fields.Char(
        compute='_compute_placeholder_code',
        search='_search_placeholder_code',
        store=False,
        help_text='Código para mostrar (Odoo placeholder_code).',
    )
    note = fields.Text(
        blank=True,
        default='',
        help_text='Notas internas (Odoo note).',
    )
    #: ≙ ``tag_ids`` (``odoo19c: account_account.py:104-112``), que la fuente
    #: declara ``compute='_compute_account_tags', readonly=False, store=True,
    #: precompute=True``.
    #:
    #: Los tres primeros se portan verbatim. El cuarto **no se puede**: una
    #: tabla intermedia necesita el ``pk`` de una fila que antes del ``INSERT``
    #: no existe. La fuente no tiene el problema porque su ORM asigna el id
    #: antes de ejecutar la cola de recálculo. El motor lo apaga con su aviso
    #: (``orm/fields_nonstored.py:_apply_precompute_block``) en vez de
    #: aceptarlo en silencio, así que declararlo aquí sería declarar algo que
    #: no ocurre. Sucesor del adelanto: tarea **#312**.
    tags = fields.Many2many(
        'account.AccountAccountTag',
        blank=True,
        related_name='accounts',
        db_table='account_account_account_tag',
        compute='_compute_account_tags',
        store=True,
        readonly=False,
        help_text=(
            'Etiquetas de reporte de la cuenta (Odoo tag_ids). Una '
            'cuenta sin etiqueta propia hereda las de la cuenta de '
            'código inmediatamente anterior.'
        ),
    )

    class Meta:
        db_table = 'account_account'
        # El orden es ``_order`` (``code, placeholder_code``), que el ORM
        # resuelve con ``_field_to_sql``; ``code`` no tiene columna que dar a
        # Django.
        ordering = ['id']
        verbose_name = 'Cuenta contable'
        verbose_name_plural = 'Cuentas contables'

    def __str__(self) -> str:
        return f'{self.code} {self.name}'

    @api.depends('account_type')
    def _compute_internal_group(self):
        # Odoo _compute_internal_group: el grupo es el prefijo del account_type
        # ('asset_receivable' -> 'asset'; 'off_balance' -> 'off').
        for account in self:
            account_type = account.account_type or ''
            account.internal_group = (
                account_type.split('_')[0] if account_type else '')

    @classmethod
    def _get_closest_parent_account(
        cls, accounts_to_process, field_name, default_value
    ):
        """El valor de la cuenta de código inmediatamente anterior.

        ≙ ``_get_closest_parent_account`` (``odoo19c: account_account.py:613``,
        ``odoo-tools@622ddc2a``). El plan de cuentas es una jerarquía **por
        código**: ``4420`` cuelga de ``4410`` sin que ninguna columna lo
        declare. Por eso el CSV del plan genérico sólo etiqueta 13 de sus 46
        cuentas — las otras 33 heredan de su vecina anterior.

        La búsqueda es la misma: las cuentas de la empresa activa
        (``_check_company_domain(env.company)``) ordenadas por código, y
        ``bisect_left`` sobre esa lista.

        Devuelve una **lista alineada con la entrada** en vez de escribir el
        campo, por dos razones que la referencia no tiene: una relación M2M no
        se puede asignar antes de que la fila exista, y una cuenta todavía sin
        ``pk`` no es hasheable, así que tampoco sirve de clave.
        """
        environment = env()
        domain = cls._check_company_domain(environment.company)
        all_accounts = environment['account.account'].sudo().search(
            domain, order='code')
        accounts_with_codes = {}
        for parent in all_accounts:
            accounts_with_codes[parent.code] = parent
        codes_list = list(accounts_with_codes)
        out = []
        for account in accounts_to_process:
            closest_index = bisect_left(codes_list, account.code) - 1
            if closest_index == -1:
                out.append(default_value)
                continue
            parent = accounts_with_codes[codes_list[closest_index]]
            if cls._meta.get_field(field_name).many_to_many:
                # La tabla, no el descriptor: leer el campo calculado lo
                # recomputaría sobre el recordset que se está calculando.
                value = list(models.related_manager(parent, field_name).all())
            else:
                value = getattr(parent, field_name)
            out.append(value)
        return out

    @api.depends('code')
    def _compute_account_type(self):
        """Hereda el tipo de la cuenta anterior — ≙ ``_compute_account_type``.

        ≙ ``odoo19c: account_account.py:603-606`` (``odoo-tools@622ddc2a``). El
        segundo consumidor de ``_get_closest_parent_account``, con el mismo
        criterio que las etiquetas: la jerarquía del plan es el código.

        **Requerido y computado no se contradicen.** La referencia declara el
        campo ``required=True`` *y* ``compute=… precompute=True`` a la vez
        (``account_account.py:104-126``): el cómputo corre **antes** del
        insert,
        así que rellena lo que el usuario no puso y la exigencia se comprueba
        después. Aquí el orden lo fija ``save``, que lo llama antes de guardar.
        Por eso esto **no** cambia el contrato del campo: el serializer lo
        sigue
        exigiendo, y el modelo sólo cubre el caso de la carga masiva.

        ``asset_current`` es el default de la referencia cuando no hay cuenta
        anterior — la primera del plan.
        """
        accounts_to_process = [
            account for account in self
            if account.code and not account.account_type
        ]
        values = self._get_closest_parent_account(
            accounts_to_process, 'account_type', 'asset_current')
        for account, account_type in zip(accounts_to_process, values):
            account.account_type = account_type or 'asset_current'

    @api.depends('code')
    def _compute_account_tags(self):
        """
        Hereda las etiquetas de la cuenta anterior — ≙
        ``_compute_account_tags``.

        Corre **después** de guardar, no antes: sin ``pk`` no hay tabla
        intermedia que poblar. La referencia lo resuelve con ``precompute`` de
        su ORM; aquí el orden lo fija ``save``.

        Una cuenta que ya trae etiquetas propias no se toca — es la guarda
        ``not account.tag_ids`` de la referencia, y lo que hace que el valor
        explícito del CSV gane sobre el heredado.
        """
        accounts_to_process = [
            account for account in self
            if account.code
            and not models.related_manager(account, 'tags').exists()
        ]
        values = self._get_closest_parent_account(
            accounts_to_process, 'tags', [])
        for account, tags in zip(accounts_to_process, values):
            if tags:
                models.related_manager(account, 'tags').set(tags)

    @staticmethod
    def _root_company_id(company):
        """La raíz de ``company``, la clave de ``code_store``."""
        return company.root_id.pk if company is not None else None

    def _authorized_company_ids(self):
        """Las empresas del usuario — ``self.env.user._get_company_ids()``.

        Sin usuario (procesos internos, pruebas) no hay a quién acotar, y
        devuelve ``None``: se consideran todas las empresas de la cuenta.
        """
        user = self.env.user
        if user is None or getattr(user, 'pk', None) is None:
            return None
        return tuple(user._get_company_ids())

    @api.depends_context('company')
    @api.depends('code_store')
    def _compute_code(self):
        """≙ ``_compute_code``
        (``odoo19c: addons/account/models/account_account.py:333-338``): el
        valor de ``code_store`` en la raíz de la empresa activa."""
        with company_scope(self._root_company_id(self.env.company)):
            for account in self:
                account.code = account.code_store or False

    def _search_code(self, operator, value):
        """≙ ``_search_code`` (``:340-341``): busca en ``code_store`` con la
        raíz de la empresa activa."""
        with company_scope(self._root_company_id(self.env.company)):
            found = self.env['account.account'].sudo().with_context(
                active_test=False)._search([('code_store', operator, value)])
        return [('id', 'in', found)]

    def _inverse_code(self):
        """≙ ``_inverse_code`` (``:343-353``): escribe ``code_store`` en la
        raíz de la empresa activa, que comparten todas sus sucursales."""
        # El valor se lee en la empresa activa —``code`` depende de ella— y
        # se escribe en su raíz, como ``zip(self, self.with_company(root))``.
        codes = [(account, account.code) for account in self]
        root = str(self._root_company_id(self.env.company))
        rows = type(self).objects.filter(pk__in=[a.id for a in self])
        stored_maps = dict(rows.values_list('pk', 'code_store'))
        for account, code in codes:
            stored = dict(stored_maps.get(account.id) or {})
            stored[root] = code
            # La fila, no ``save``: el ``save`` de este modelo recalcula el
            # tipo y el grupo, y la fuente sólo escribe ``code_store``.
            type(self).objects.filter(pk=account.id).update(
                code_store=stored)
        # ≙ ``invalidate_recordset(fnames=['code'], flush=False)`` y el
        # recálculo inmediato (``:351-353``): todas las empresas de la raíz
        # leen el valor nuevo.
        self.invalidate_recordset(fnames=['code'], flush=False)

    @api.depends('code', 'code_store')
    def _compute_placeholder_code(self):
        """≙ ``_compute_placeholder_code``
        (``odoo19c: addons/account/models/account_account.py:355-365``).

        El código leído en la raíz de la empresa activa; si la cuenta no la
        tiene, el de su primera empresa autorizada seguido de su nombre.
        """
        active_root = self._root_company_id(self.env.company)
        authorized = self._authorized_company_ids()
        # El mapa de la tabla, de una vez: una instancia del lote puede no
        # traer ``code_store`` cargado, y el descriptor sólo da el valor de
        # la empresa activa.
        stored_maps = dict(
            type(self).objects.filter(pk__in=[a.pk for a in self if a.pk])
            .values_list('pk', 'code_store'))
        for account in self:
            stored = stored_maps.get(account.pk) or {}
            account.placeholder_code = False
            if active_root is not None and stored.get(str(active_root)):
                account.placeholder_code = stored[str(active_root)]
                continue
            companies = sorted(
                (company for company
                 in models.related_manager(account, 'company_ids').all()
                 if authorized is None or company.pk in authorized),
                key=lambda company: company.pk,
            )
            if not companies:
                continue
            company = companies[0]
            code = stored.get(str(self._root_company_id(company)))
            if code:
                account.placeholder_code = f'{code} ({company.name})'

    def _search_placeholder_code(self, operator, value):
        """≙ ``_search_placeholder_code``
        (``odoo19c: addons/account/models/account_account.py:367-377``)."""
        if operator not in ('=ilike', 'in'):
            return NotImplemented
        query = Query(self.env, 'account_account')
        placeholder_code_sql = self._field_to_sql(
            'account_account', 'placeholder_code', query)
        if operator == 'in':
            query.add_where(SQL("%s = ANY(%s)", placeholder_code_sql,
                                list(value)))
        else:
            query.add_where(SQL("%s ILIKE %s", placeholder_code_sql, value))
        return [('id', 'in', query)]

    def _field_to_sql(self, alias, field_expr, query=None):
        """≙ ``_field_to_sql``
        (``odoo19c: addons/account/models/account_account.py:130-186``), la
        rama de ``placeholder_code``.

        La primera empresa autorizada de la cuenta se une una sola vez por
        consulta, con el alias ``account_first_company`` de la fuente.
        """
        if field_expr == 'code':
            # ≙ la rama ``code`` (``:131-132``): ``code_store`` en la raíz.
            with company_scope(self._root_company_id(self.env.company)):
                return super()._field_to_sql(alias, 'code_store', query)
        if field_expr != 'placeholder_code':
            return super()._field_to_sql(alias, field_expr, query)
        authorized = self._authorized_company_ids()
        if 'account_first_company' not in query._joins:
            company_filter = (
                SQL("WHERE rel.rescompany_id = ANY(%s)", list(authorized))
                if authorized is not None else SQL())
            query.add_join(
                'LEFT JOIN',
                'account_first_company',
                SQL(
                    """(
                        SELECT DISTINCT ON (rel.accountaccount_id)
                            rel.accountaccount_id AS account_id,
                            rel.rescompany_id AS company_id,
                            COALESCE(
                                NULLIF(SPLIT_PART(res_company.parent_path,
                                                  '/', 1), ''),
                                res_company.id::text) AS root_company_id,
                            res_partner.name AS company_name
                        FROM account_account_res_company_rel rel
                        JOIN res_company
                            ON res_company.id = rel.rescompany_id
                        JOIN res_partner
                            ON res_partner.id = res_company.partner_id
                        %(company_filter)s
                        ORDER BY rel.accountaccount_id, company_id
                    )""",
                    company_filter=company_filter,
                ),
                SQL('account_first_company.account_id = %(account_id)s',
                    account_id=SQL.identifier(alias, 'id')),
            )
        active_root = self._root_company_id(self.env.company)
        return SQL(
            """
                COALESCE(
                    %(code_store)s->>%(active_company_root_id)s,
                    %(code_store)s->>%(account_first_company_root_id)s
                        || ' (' || %(account_first_company_name)s || ')'
                )
            """,
            code_store=SQL.identifier(alias, 'code_store'),
            active_company_root_id=str(active_root or ''),
            account_first_company_name=SQL.identifier(
                'account_first_company', 'company_name'),
            account_first_company_root_id=SQL.identifier(
                'account_first_company', 'root_company_id'),
        )

    def save(self, *args, **kwargs):
        # El orden importa y es el de la referencia: el tipo se computa antes
        # que el grupo, que lo deriva; y las etiquetas después de guardar,
        # porque una relación M2M necesita la fila creada.
        # En alta el tipo es precompute (pase de ``pre_save``) y el grupo lo
        # calcula el marcado de creación tras el INSERT, como en la fuente;
        # invocarlos aquí además los repetía
        # (designs/eager-computes-in-save.md). En modificación se conservan.
        if not self._state.adding:
            self._compute_account_type()
            self._compute_internal_group()
        result = super().save(*args, **kwargs)
        companies = models.related_manager(self, 'company_ids')
        if self.company_id and not companies.filter(
                pk=self.company_id).exists():
            companies.add(self.company_id)
        self._compute_account_tags()
        return result

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create``
        (``odoo19c: addons/account/models/account_account.py:1011-1051``).

        Agrupa las altas por su ``company_ids``, resuelve las empresas con la
        activa primero (:meth:`_resolve_companies`) y traduce
        ``prefix``/``code_digits`` al primer código libre en la primera
        empresa. Crea con las empresas resueltas activas, el
        ``allowed_company_ids=companies.ids`` de la fuente (``:1042-1047``).
        Divergencias declaradas en ``designs/account-account-mc2b.md``:
        ``code_mapping_ids`` no viaja y ``_ensure_code_is_unique`` llega con
        MC2c-2. Hasta MC2c-2 la columna ``company`` toma la primera empresa
        resuelta.
        """
        if not vals_list:
            return super().create(vals_list)
        records_list = []
        for company_ids, vals_list_for_company in itertools.groupby(
                vals_list, lambda vals: vals.get('company_ids', [])):
            cache = set()
            vals_list_for_company = list(vals_list_for_company)
            companies = cls._resolve_companies(company_ids)
            for vals in vals_list_for_company:
                if 'prefix' in vals:
                    prefix = vals.pop('prefix') or ''
                    digits = vals.pop('code_digits')
                    start_code = (prefix.ljust(digits - 1, '0') + '1'
                                  if len(prefix) < digits else prefix)
                    vals['code'] = cls.search_new_account_code(
                        start_code, companies[0] if companies else None,
                        cache)
                    cache.add(vals['code'])
                vals['company_ids'] = [fields.Command.set(
                    [company.pk for company in companies])]
                if companies:
                    vals.setdefault('company', companies[0])
            without_type = [index for index, vals
                            in enumerate(vals_list_for_company)
                            if not vals.get('account_type')]
            with company_scope([company.pk for company in companies]):
                created = super().create(vals_list_for_company)
                # Divergencia de mecanismo, declarada: la fuente precalcula
                # el tipo con el ``code`` dado ya en la caché; aquí el código
                # vive en ``code_store``, que el inverso escribe tras la
                # inserción, así que el tipo heredado se calcula después.
                if without_type:
                    pending = created.browse(
                        [created.ids[index] for index in without_type])
                    pending._compute_account_type()
                    pending.flush_recordset(['account_type'])
                records_list.append(created)
        records = records_list[0].union(*records_list[1:])
        records._ensure_code_is_unique()
        return records

    def write(self, vals):
        """≙ ``write``
        (``odoo19c: addons/account/models/account_account.py:1053-1077``),
        la rama de unicidad: tras escribir ``company_ids`` o ``code`` se
        verifica el código (``:1072-1077``).

        Pendiente, con su razón: las otras tres ramas de la fuente —el paso
        de ``reconcile`` (``_toggle_reconcile_to_true/false``), la moneda
        con apuntes en otra divisa y la cuenta usada en una línea de reparto
        al deprecarla— dependen de métodos que este árbol no tiene; su
        sucesor está en ``designs/account-account-mc2c.md``.
        """
        result = super().write(vals)
        if {'company_ids', 'code'} & vals.keys():
            self._ensure_code_is_unique()
        return result

    def _ensure_code_is_unique(self):
        """≙ ``_ensure_code_is_unique`` (``:1079-1130``).

        1. Cada empresa de la cuenta tiene su código.
        2. Ninguna empresa madre o hija tiene otra cuenta con el mismo
           código, ni dentro del lote ni en la base.
        """
        accounts = self.sudo()
        for account in accounts:
            roots = {self._root_company_id(company)
                     for company in models.related_manager(
                         account, 'company_ids').all()}
            for root in roots:
                with company_scope(root):
                    if not type(self).objects.get(pk=account.id).code:
                        raise ValidationError(_(
                            "The code must be set for every company to "
                            "which this account belongs."))
        account_ids_by_company = {}
        for account in accounts:
            for company in models.related_manager(
                    account, 'company_ids').all():
                account_ids_by_company.setdefault(company, []).append(
                    account.id)
        for company, account_ids in account_ids_by_company.items():
            with company_scope(company.pk):
                batch = self.env['account.account'].sudo().browse(
                    account_ids)
                accounts_by_code = batch.grouped('code')
                duplicate_codes = None
                if len(accounts_by_code) < len(batch):
                    duplicate_codes = [
                        code for code, grouped in accounts_by_code.items()
                        if len(grouped) > 1]
                else:
                    duplicates = self.env['account.account'].sudo(
                    ).with_context(active_test=False).search([
                        ('code', 'in', list(accounts_by_code)),
                        ('id', 'not in', self.ids),
                        '|',
                        ('company_ids', 'parent_of', company.pk),
                        ('company_ids', 'child_of', company.pk),
                    ])
                    if duplicates:
                        duplicate_codes = duplicates.mapped('code')
            if duplicate_codes:
                raise ValidationError(_(
                    "Account codes must be unique. You can't create "
                    "accounts with these duplicate codes: %s",
                    ", ".join(duplicate_codes)))

    @classmethod
    def _resolve_companies(cls, company_ids):
        """Las empresas de un alta, con la activa primero — el paso de
        ``create`` (``:1018-1022``): la activa encabeza cuando está entre las
        pedidas o no se pidió ninguna.

        ``company_ids`` llega como comandos (``SET``, ``LINK``), ids sueltos
        o filas, lo que ``convert_to_cache`` lee en la fuente.
        """
        ids = []
        for command in company_ids or []:
            if isinstance(command, (list, tuple)):
                if command[0] == fields.Command.SET:
                    ids = [getattr(item, 'pk', item) for item in command[2]]
                elif command[0] == fields.Command.LINK:
                    ids.append(command[1])
            else:
                ids.append(getattr(command, 'pk', command))
        found = {company.pk: company
                 for company in ResCompany.objects.filter(pk__in=ids)}
        companies = [found[pk] for pk in ids if pk in found]
        active = env().company
        if active is not None and (active.pk in found or not companies):
            companies = [active] + [company for company in companies
                                    if company.pk != active.pk]
        return companies

    @classmethod
    def search_new_account_code(cls, start_code, company, cache=None):
        """
        El primer código libre a partir de ``start_code`` — ≙
        ``_search_new_account_code``.

        Es lo que permite declarar una cuenta por **prefijo** en vez de por
        código: la plantilla dice "la cuenta transitoria de banco va bajo
        1014" y este método encuentra el primer hueco. Comportamiento de la
        referencia (``odoo19c: account_account.py:466-540``), incluidos sus
        dos casos de borde:

        - se incrementa **la cola numérica**, conservando el ancho:
          ``102100 → 102101``; ``1021A`` no tiene cola, así que incrementa el
          número que la precede (``1022A``);
        - si no queda hueco —o el código no termina en dígito— cae a
          ``<code>.copy``, ``.copy2`` … hasta ``.copy99``.

        ``cache`` son los códigos que quien llama ya reservó pero aún no
        escribió; sin él, dos cuentas creadas en la misma tanda tomarían el
        mismo hueco.
        """
        if cache is None:
            cache = {start_code}

        def is_free(code):
            # ≙ ``code_is_available``
            # (``odoo19c: account_account.py:509-526``): libre si ninguna
            # cuenta con ese código pertenece a una empresa madre o hija de
            # ``company``.
            if code in cache:
                return False
            if company is None:
                return True
            with company_scope(company.pk):
                return not env()['account.account'].sudo().with_context(
                    active_test=False).search_count([
                        ('code', '=', code),
                        '|',
                        ('company_ids', 'parent_of', company.pk),
                        ('company_ids', 'child_of', company.pk),
                    ], limit=1)

        if is_free(start_code):
            return start_code

        head = start_code.rstrip('0123456789')
        tail = start_code[len(head):]
        if tail:
            width = len(tail)
            for number in range(int(tail) + 1, 10**width):
                candidate = f'{head}{number:0{width}d}'
                if is_free(candidate):
                    return candidate
        else:
            # Sin cola numérica: la referencia incrementa el número que
            # precede al sufijo no numérico (``1021A`` → ``1022A``).
            stem = start_code.rstrip(
                'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
            )
            suffix = start_code[len(stem):]
            inner = stem.rstrip('0123456789')
            digits = stem[len(inner):]
            if digits:
                width = len(digits)
                for number in range(int(digits) + 1, 10**width):
                    candidate = f'{inner}{number:0{width}d}{suffix}'
                    if is_free(candidate):
                        return candidate

        for n in [''] + [str(i) for i in range(2, 100)]:
            candidate = f'{start_code}.copy{n}'
            if is_free(candidate):
                return candidate
        raise UserError(
            _('No hay código disponible a partir de «%(code)s».')
            % {'code': start_code}
        )

    @api.ondelete(at_uninstall=False)
    def _unlink_except_linked_to_fiscal_position(self):
        """≙ ``_unlink_except_linked_to_fiscal_position`` (``odoo19c:
        addons/account/models/account_account.py:1142-1145``): una cuenta
        mapeada por una posición fiscal no se borra; el mensaje de la fuente
        llega antes que el ``ProtectedError`` del mapeo."""
        mapping = apps.get_model('account', 'AccountFiscalPositionAccount')
        if mapping.objects.filter(
                Q(account_src=self) | Q(account_dest=self)).exists():
            raise UserError(_(
                'You cannot remove/deactivate the accounts "%s" which are set '
                'on the account mapping of a fiscal position.',
                f'{self.code} - {self.name}'))
