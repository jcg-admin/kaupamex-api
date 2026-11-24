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

from bisect import bisect_left

from django.apps import apps
from django.db.models import Q

import api
import fields
import models
from exceptions import UserError
from tools.translate import _


class AccountAccount(models.RecordLoaderMixin, models.Model):
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
    #: plural porque su cuenta lleva el M2M ``company_ids``; aquí la cuenta
    #: tiene una sola ``company``, y el plural devolvería ``None`` —el modelo
    #: dejaría de participar en la comprobación de empresa—. El singular
    #: ``check_company_domain_parent_of`` conserva el criterio jerárquico de
    #: la fuente sobre el campo que existe. Se cambia al plural cuando
    #: ``company_ids`` esté portado.
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

    code = fields.Char(
        max_length=64,
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
        ordering = ['code']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='unique_account_code_company',
            ),
        ]
        verbose_name = 'Cuenta contable'
        verbose_name_plural = 'Cuentas contables'

    def __str__(self) -> str:
        return f'{self.code} {self.name}'

    @api.depends('account_type')
    def _compute_internal_group(self):
        # Odoo _compute_internal_group: el grupo es el prefijo del account_type
        # ('asset_receivable' -> 'asset'; 'off_balance' -> 'off').
        at = self.account_type or ''
        self.internal_group = at.split('_')[0] if at else ''

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

        La búsqueda es la misma: todas las cuentas de la empresa ordenadas por
        código, y ``bisect_left`` sobre esa lista.

        Devuelve una **lista alineada con la entrada** en vez de escribir el
        campo, por dos razones que la referencia no tiene: una relación M2M no
        se puede asignar antes de que la fila exista, y una cuenta todavía sin
        ``pk`` no es hasheable, así que tampoco sirve de clave.
        """
        codes_of_the_company = {}
        out = []
        for account in accounts_to_process:
            if not account.code:
                out.append(default_value)
                continue
            company = account.company
            if company.pk not in codes_of_the_company:
                codes_of_the_company[company.pk] = list(
                    cls.objects.filter(company=company)
                    .order_by('code')
                    .values_list('pk', 'code')
                )
            rows = codes_of_the_company[company.pk]
            closest_index = (
                bisect_left([code for _pk, code in rows], account.code) - 1
            )
            if closest_index == -1:
                out.append(default_value)
                continue
            value = getattr(
                cls.objects.get(pk=rows[closest_index][0]), field_name
            )
            out.append(list(value.all()) if hasattr(value, 'all') else value)
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
        if not self.code or self.account_type:
            return
        self.account_type = (
            self._get_closest_parent_account(
                [self], 'account_type', 'asset_current'
            )[0]
            or 'asset_current'
        )

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
        if not self.code or self.tags.exists():
            return
        tags = self._get_closest_parent_account([self], 'tags', [])[0]
        if tags:
            self.tags.set(tags)

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
        update_fields = kwargs.get('update_fields')
        if update_fields is None or {'code', 'company'} & set(update_fields):
            self._sync_code_store()
            if update_fields is not None:
                kwargs['update_fields'] = {*update_fields, 'code_store'}
        result = super().save(*args, **kwargs)
        if self.company_id and self.company_id not in self.company_ids.ids:
            self.company_ids.add(self.company_id)
        self._compute_account_tags()
        return result

    def _sync_code_store(self):
        """Escribe ``code`` bajo la empresa raíz de ``company``.

        ≙ ``_inverse_code``
        (``odoo19c: addons/account/models/account_account.py:344-355``), que
        escribe ``code_store`` con la empresa raíz activa. En MC1
        ``code`` sigue siendo columna, así que el inverso se aplica al
        guardar en vez de al asignar.
        """
        if not self.company_id or not self.code:
            return
        field = self._meta.get_field('code_store')
        field.set_for_company(self, self.company.root_id.pk, self.code)

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
            return (
                code not in cache
                and not cls.objects.filter(company=company, code=code).exists()
            )

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
