"""``account.fiscal.position`` — posición fiscal (Odoo ``account``).

Adaptación de Odoo addons/account/models/partner.py
(odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de, odoo19c:, LGPL-3),
clase ``AccountFiscalPosition`` (odoo19c: partner.py:27-296).

Mapea impuestos y cuentas de un tercero/país a sus equivalentes locales
(p. ej. cliente extranjero → impuesto de exportación en vez del doméstico).

Campos núcleo portados: ``sequence``, ``name``, ``active``, ``company``,
``account_ids`` (reverso de ``account.fiscal.position.account``),
``tax_ids`` (M2M a ``account.tax``), ``note``, ``auto_apply``,
``vat_required``, ``country``, ``country_group``, ``state_ids``, ``zip_from``,
``zip_to``, ``foreign_vat``. Métodos ``map_tax``/``map_account`` portados
tal cual (Python puro, sin dependencia del cliente web).

**DRIFT DE VERSIÓN — NO existe `account.fiscal.position.tax` en 19.**
``odoo18c: partner.py:300-301`` declara ``AccountFiscalPositionTax`` (mapeo
impuesto-origen → impuesto-destino, tabla intermedia). Odoo 19 lo retiró: el
mapeo de impuestos ahora vive directo en ``AccountTax.original_tax_ids``/
``replacing_tax_ids`` (M2M ``account_tax_alternatives``, odoo19c:
account_tax.py:106-124) y ``AccountFiscalPosition.tax_ids`` (M2M directa,
sin línea intermedia). Como 19 gobierna (``referencia-odoo-gobierna-las-
decisiones.md``), **NO se porta** ``account.fiscal.position.tax`` — el mapeo
de impuestos usa la M2M directa ``tax_ids`` sobre la posición fiscal, con
``_compute_tax_map`` armado desde ``AccountTax.original_tax_ids`` — **portado**
en ``account_tax.py`` (H-API-322): ``_compute_tax_map`` ya no devuelve ``{}``
en todos los casos, la rama de sustitución de ``map_tax`` es operable.

NO se porta: ``account_map``/``tax_map`` (``fields.Binary(compute=...)`` —
caché de diccionario, se recalculan bajo demanda en ``map_tax``/``map_account``
en vez de cachearse en un campo); ``_get_fiscal_position``/
``_get_first_matching_fpos``/``_get_fpos_validation_functions`` (requieren
``res.partner`` con ``property_account_position_id`` y VAT — fuera de este
corte fiscal); ``foreign_vat_header_mode``/``action_create_foreign_taxes``
(banner + wizard del cliente web de Odoo, sin análogo en DRF);
``states_count`` (cuenta trivial de UI, sin uso fuera de vista).
"""

import fields
import models
from django.db.models import Q
from orm.environments import env

from addons.base.models import ResCountry
from addons.base.models.ir_model import IrModelData


class AccountFiscalPosition(models.Model):
    """
    ``account.fiscal.position`` — mapeo de impuestos/cuentas por país/tercero.
    """

    #: Atributos de clase de ``account.fiscal.position``, verbatim
    #: (``odoo19c: account/models/partner.py:27-29``).
    _name = 'account.fiscal.position'
    _description = 'Fiscal Position'
    _order = 'sequence'

    sequence = fields.Integer(
        default=10,
        help_text=(
            'Orden de emparejamiento, empresa específica primero (Odoo'
            ' sequence).'
        ),
    )
    name = fields.Char(
        max_length=255,
        help_text='Nombre de la posición fiscal (Odoo name, requerido).',
    )
    active = fields.Boolean(
        default=True,
        help_text=(
            'Posición activa; desactivar en vez de borrar (Odoo active).'
        ),
    )
    company = fields.Many2one(
        'base.ResCompany',
        null=False, on_delete=models.CASCADE,
        related_name='fiscal_positions',
        help_text='Empresa (Odoo company_id, requerido).',
    )
    tax_ids = fields.Many2many(
        'account.AccountTax',
        related_name='fiscal_positions',
        blank=True,
        db_table='account_fiscal_position_account_tax_rel',
        help_text=(
            'Impuestos destino aplicables bajo esta posición (Odoo tax_ids).'
        ),
    )
    note = fields.Text(
        blank=True,
        default='',
        help_text=(
            'Menciones legales a imprimir en la factura (Odoo note, Html en la'
            ' referencia).'
        ),
    )
    auto_apply = fields.Boolean(
        default=False,
        help_text=(
            'Aplica automáticamente si el criterio VAT/país coincide (Odoo'
            ' auto_apply).'
        ),
    )
    vat_required = fields.Boolean(
        default=False,
        help_text='Sólo aplica si el tercero tiene VAT (Odoo vat_required).',
    )
    country = fields.Many2one(
        'base.ResCountry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fiscal_positions',
        help_text='País de entrega requerido para aplicar (Odoo country_id).',
    )
    country_group = fields.Many2one(
        'base.ResCountryGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fiscal_positions',
        help_text=(
            'Grupo de países requerido para aplicar (Odoo country_group_id).'
        ),
    )
    state_ids = fields.Many2many(
        'base.ResCountryState',
        related_name='fiscal_positions',
        blank=True,
        db_table='account_fiscal_position_state_rel',
        help_text=(
            'Estados federales requeridos para aplicar (Odoo state_ids).'
        ),
    )
    zip_from = fields.Char(
        max_length=24,
        blank=True,
        default='',
        help_text='Rango de código postal, desde (Odoo zip_from).',
    )
    zip_to = fields.Char(
        max_length=24,
        blank=True,
        default='',
        help_text='Rango de código postal, hasta (Odoo zip_to).',
    )
    foreign_vat = fields.Char(
        max_length=32,
        blank=True,
        default='',
        help_text=(
            'RFC/VAT propio en la región mapeada por esta posición (Odoo'
            ' foreign_vat).'
        ),
    )

    class Meta:
        db_table = 'account_fiscal_position'
        ordering = ['sequence']
        verbose_name = 'Posición fiscal'
        verbose_name_plural = 'Posiciones fiscales'

    def __str__(self) -> str:
        return self.name

    def map_tax(self, taxes):
        """Traduce ``taxes`` a sus equivalentes bajo esta posición — Odoo
        ``map_tax`` (odoo19c: partner.py:159-165).

        Sin posición: ``taxes`` tal cual. Sin ``tax_ids`` propios: se
        excluyen los impuestos que declaran alguna posición fiscal (Odoo
        ``fiscal_position_ids``) — quedan sólo los "universales". Con
        ``tax_ids``: cada impuesto de entrada se sustituye por su destino si
        alguno de los impuestos propios lo declara como ``original_tax_ids``
        (``tax_map``). Las tres ramas son fieles y operables (H-API-322 cerró
        la de sustitución, antes inerte por ``tax_map`` siempre vacío — ver
        ``_compute_tax_map``).
        """
        if not self.pk:
            return taxes
        if not self.tax_ids.exists():
            return taxes.exclude(fiscal_positions__isnull=False)
        tax_map = self._compute_tax_map()
        seen = []
        for tax in taxes:
            for dest_id in tax_map.get(tax.pk, [tax.pk]):
                if dest_id not in seen:
                    seen.append(dest_id)
        return self.tax_ids.model.objects.filter(pk__in=seen)

    def _compute_tax_map(self):
        """Odoo ``_compute_tax_map`` (odoo19c: partner.py:99-105).

        Por cada impuesto DESTINO de esta posición (``tax_ids``), lee sus
        ``original_tax_ids`` — los impuestos ORIGEN que reemplaza — y arma
        ``{origen_pk: [destino_pk, ...]}``. Antes de H-API-322 ``AccountTax``
        no tenía ``original_tax_ids`` portado y este método devolvía ``{}``
        siempre, dejando inerte la rama de sustitución de ``map_tax``.
        """
        tax_map = {}
        for dest_tax in self.tax_ids.all().prefetch_related(
            'original_tax_ids'
        ):
            for src_tax in dest_tax.original_tax_ids.all():
                tax_map.setdefault(src_tax.pk, []).append(dest_tax.pk)
        return tax_map

    def map_account(self, account):
        """Cuenta destino para ``account`` bajo esta posición — Odoo
        ``map_account`` (odoo19c: partner.py:167-168)."""
        if account is None:
            return account
        mapping = {
            row.account_src_id: row.account_dest
            for row in self.account_ids.select_related('account_dest').all()
        }
        return mapping.get(account.pk, account)

    # -- resolución automática (odoo19c: partner.py:208-280) ---------------

    @classmethod
    def _get_first_matching_fpos(cls, fiscal_positions, partner):
        """≙ ``_get_first_matching_fpos`` (``odoo19c: partner.py:208-213``).

        La primera de ``fiscal_positions`` que pasa las cinco validaciones
        para ``partner``: primero las de la empresa más específica (más
        empresas madre), luego por ``sequence``. Sin ninguna, la posición
        vacía (``cls()``, cuyo ``map_tax`` deja los impuestos tal cual).

        **Divergencia de receptor, declarada:** la fuente recorre ``self``;
        aquí el conjunto llega como argumento, porque el modelo es de Django
        y su instancia es una sola fila.
        """
        def specificity(fpos):
            company = fpos.company
            return (-len(company.parent_ids) if company else 0,
                    fpos.sequence)
        checks = cls._get_fpos_validation_functions(partner)
        for fpos in sorted(fiscal_positions, key=specificity):
            if all(check(fpos) for check in checks):
                return fpos
        return cls()

    @classmethod
    def _get_fpos_validation_functions(cls, partner):
        """≙ ``_get_fpos_validation_functions`` (``odoo19c: partner.py:
        215-243``): VAT exigido, rango de código postal, estado, país y
        grupo de países (con sus estados excluidos)."""
        company = env().company

        def in_country_group(fpos):
            group = fpos.country_group
            if group is None:
                return True
            if partner.country_id not in set(
                    group.country_ids.values_list('pk', flat=True)):
                return False
            excluded = set(
                group.exclude_state_ids.values_list('pk', flat=True))
            return not partner.state_id or partner.state_id not in excluded

        return [
            lambda fpos: (not fpos.vat_required
                          or partner._get_vat_required_valid(company=company)),
            lambda fpos: (not (fpos.zip_from and fpos.zip_to)
                          or (partner.zip and fpos.zip_from <= partner.zip
                              <= fpos.zip_to)),
            lambda fpos: (not fpos.state_ids.exists()
                          or fpos.state_ids.filter(
                              pk=partner.state_id).exists()),
            lambda fpos: (fpos.country_id is None
                          or partner.country_id == fpos.country_id),
            in_country_group,
        ]

    @classmethod
    def _get_fiscal_position(cls, partner, delivery=None):
        """≙ ``_get_fiscal_position`` (``odoo19c: partner.py:245-280``).

        La posición fiscal de ``partner``: la que el socio declara a mano y,
        si no hay, la primera automática (``auto_apply``) de la empresa
        activa que valide para la dirección de entrega.

        **Divergencia declarada:** en la fuente
        ``property_account_position_id`` depende de la empresa
        (``with_company``); aquí es una FK simple del socio
        (``account/models/partner.py``), así que se lee sin empresa.
        """
        if not partner:
            return cls()
        company = env().company
        intra_eu = vat_exclusion = False
        company_vat = company.vat if company else ''
        if company_vat and partner.vat:
            europe = IrModelData._xmlid_to_res_id('base.europe')
            eu_country_codes = set(ResCountry.objects.filter(
                country_groups=europe).values_list('code', flat=True)) \
                if europe else set()
            eu_country_codes = {code.upper() for code in eu_country_codes}
            intra_eu = (company_vat[:2].upper() in eu_country_codes
                        and partner.vat[:2].upper() in eu_country_codes)
            vat_exclusion = company_vat[:2] == partner.vat[:2]
        if not delivery or (intra_eu and vat_exclusion
                            and partner.country_id == company.country_id):
            delivery = partner
        manual_fiscal_position = (delivery.property_account_position_id
                                  or partner.property_account_position_id)
        if manual_fiscal_position:
            return manual_fiscal_position
        if not partner.country_id:
            return cls()
        candidates = cls.objects.filter(auto_apply=True).filter(
            Q(company__isnull=True)
            | Q(company__in=company.parent_ids if company else []))
        return cls._get_first_matching_fpos(candidates, delivery)
