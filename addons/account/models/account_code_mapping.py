"""``account.code.mapping`` — los códigos de una cuenta por empresa.

Adaptación de ``odoo19c: addons/account/models/account_code_mapping.py``
(LGPL-3, copia y adaptación con atribución). Modelo sólo de interfaz, sin
tabla ni filas (``_auto = False``, ``_table_query = '0'``): sus registros se
fabrican con el id ``account_id * COMPANY_OFFSET + company_id`` (``:6``) y
viven sólo en la caché.

Hasta MC2c este archivo declaraba la divergencia porque la cuenta tenía una
sola empresa. Desde MC2b–MC2c-2 la cuenta tiene ``company_ids`` y su código
vive por empresa raíz en ``code_store``: la premisa de la fuente existe y el
modelo se porta (``designs/account-code-mapping.md``).

Divergencia de mecanismo declarada: ``Meta.managed = False`` con un
``db_table`` simbólico, porque Django exige una tabla nominal para un modelo
concreto; ningún código de este modelo la consulta.
"""
from django.db import models as dj_models

import api
import fields
import models
from addons.base.models import ResCompany
from exceptions import UserError
from orm.domains import Domain
from orm.environments import company_scope, env
from tools.translate import _

COMPANY_OFFSET = 10000


class AccountCodeMapping(models.BaseModel):
    """≙ ``AccountCodeMapping`` (``:9-86``)."""

    _name = 'account.code.mapping'
    _description = "Mapping of account codes per company"
    _auto = False
    _table_query = '0'

    account_id = fields.Many2one(
        'account.AccountAccount', store=False,
        compute='_compute_account_id', on_delete=dj_models.DO_NOTHING,
        related_name='+', string="Account")
    company_id = fields.Many2one(
        'base.ResCompany', store=False, compute='_compute_company_id',
        on_delete=dj_models.DO_NOTHING, related_name='+', string="Company")
    code = fields.Char(
        store=False, compute='_compute_code', inverse='_inverse_code',
        string="Code")

    class Meta:
        managed = False
        db_table = 'account_code_mapping'

    @classmethod
    def _mapping_id(cls, account_id, company_id):
        """El id virtual de la fila (cuenta, empresa): ``:42`` y ``:65``.

        La fuente supone pks de empresa menores que ``COMPANY_OFFSET``; con uno
        mayor, ``//`` y ``%`` decodificarían otra cuenta y otra empresa sin
        error. Divergencia declarada: aquí se rehúsa en vez de devolverlas
        (``designs/account-code-mapping.md``).
        """
        if company_id >= COMPANY_OFFSET:
            raise UserError(_(
                "Account Code Mapping supports companies with an id below "
                "%(offset)s; company %(company)s is past that limit.",
                offset=COMPANY_OFFSET, company=company_id))
        return account_id * COMPANY_OFFSET + company_id

    @api.model_create_multi
    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``:39-47``): devuelve los registros de los ids
        sintéticos y escribe su ``code``, que dispara el inverso."""
        mappings = env()[cls._name].browse([
            cls._mapping_id(vals['account_id'], vals['company_id'])
            for vals in vals_list
        ])
        for mapping, vals in zip(mappings, vals_list):
            mapping.write({'code': vals['code']})
        return mappings

    @classmethod
    def _search(cls, domain, offset=0, limit=None, order=None, **kw):
        """≙ ``_search`` (``:49-67``): exige ``('account_id', 'in', ids)``
        y devuelve cuenta × empresas activas del usuario (por ``sequence,
        name``) filtradas por el resto del dominio."""
        account_ids = []

        def get_accounts(condition):
            if (not account_ids and condition.field_expr == 'account_id'
                    and condition.operator == 'in'):
                account_ids.extend(condition.value)
                return Domain(bool(condition.value))
            return condition

        remaining_domain = Domain(domain).map_conditions(get_accounts)
        if not account_ids:
            raise UserError(_(
                "Account Code Mapping cannot be accessed directly. "
                "It is designed to be used only through the Chart of "
                "Accounts."
            ))
        # ``res.users`` es aquí un modelo de Django: el
        # ``with_context(active_test=True).company_ids.sorted(...)`` de la
        # fuente es el filtro ``active`` y el orden ``sequence, name``
        # (``name`` es el ``related='partner_id.name'`` de la empresa).
        companies = env().user.company_ids.filter(active=True).order_by(
            'sequence', 'partner__name')
        return env()[cls._name].browse([
            cls._mapping_id(account_id, company.id)
            for account_id in account_ids
            for company in companies
        ]).filtered_domain(remaining_domain)._as_query()

    def _compute_account_id(self):
        """≙ ``_compute_account_id`` (``:69-71``). La fuente asigna el id y su
        ``convert_to_cache`` lo vuelve registro; aquí se asigna el registro."""
        accounts = self.env['account.account']
        for record in self:
            record.account_id = accounts.browse(
                record._origin.id // COMPANY_OFFSET)

    def _compute_company_id(self):
        """≙ ``_compute_company_id`` (``:73-75``). ``res.company`` es aquí un
        modelo de Django: se asigna su instancia."""
        ids = {record._origin.id % COMPANY_OFFSET for record in self}
        companies = ResCompany.objects.in_bulk(ids)
        for record in self:
            record.company_id = companies.get(
                record._origin.id % COMPANY_OFFSET)

    @api.depends('account_id.code')
    def _compute_code(self):
        """≙ ``_compute_code`` (``:77-81``).

        Divergencia de mecanismo declarada: la fuente lee
        ``account.with_company(company).code``; aquí ``env.company`` sale de
        ``company_scope``, no del contexto ``allowed_company_ids`` que
        ``with_company`` escribe, así que el código se lee bajo
        ``company_scope(company)``.
        """
        for record in self:
            with company_scope(record.company_id.pk):
                record.code = record.account_id.code

    def _inverse_code(self):
        """≙ ``_inverse_code`` (``:83-86``), bajo ``company_scope`` por la
        misma razón que :meth:`_compute_code`."""
        for record in self:
            code = record.code
            with company_scope(record.company_id.pk):
                record.account_id.write({'code': code})
