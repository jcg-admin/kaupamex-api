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
``_compute_tax_map`` armado desde ``AccountTax.original_tax_ids`` (no
portado en este pase: pendiente de ``account.tax`` con
``original_tax_ids``/``replacing_tax_ids``; declarado, no fabricado).

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


class AccountFiscalPosition(models.Model):
    """``account.fiscal.position`` — mapeo de impuestos/cuentas por país/tercero."""

    sequence         = fields.Integer(
        default=10, help_text='Orden de emparejamiento, empresa específica primero (Odoo sequence).',
    )
    name              = fields.Char(
        max_length=255, help_text='Nombre de la posición fiscal (Odoo name, requerido).',
    )
    active             = fields.Boolean(
        default=True, help_text='Posición activa; desactivar en vez de borrar (Odoo active).',
    )
    company             = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='fiscal_positions',
        help_text='Empresa (Odoo company_id, requerido).',
    )
    tax_ids               = fields.Many2many(
        'account.AccountTax', related_name='fiscal_positions', blank=True,
        db_table='account_fiscal_position_account_tax_rel',
        help_text='Impuestos destino aplicables bajo esta posición (Odoo tax_ids).',
    )
    note                    = fields.Text(
        blank=True, default='',
        help_text='Menciones legales a imprimir en la factura (Odoo note, Html en la referencia).',
    )
    auto_apply                = fields.Boolean(
        default=False,
        help_text='Aplica automáticamente si el criterio VAT/país coincide (Odoo auto_apply).',
    )
    vat_required                = fields.Boolean(
        default=False, help_text='Sólo aplica si el tercero tiene VAT (Odoo vat_required).',
    )
    country                       = fields.Many2one(
        'base.ResCountry', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fiscal_positions',
        help_text='País de entrega requerido para aplicar (Odoo country_id).',
    )
    country_group                  = fields.Many2one(
        'base.ResCountryGroup', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fiscal_positions',
        help_text='Grupo de países requerido para aplicar (Odoo country_group_id).',
    )
    state_ids                       = fields.Many2many(
        'base.ResCountryState', related_name='fiscal_positions', blank=True,
        db_table='account_fiscal_position_state_rel',
        help_text='Estados federales requeridos para aplicar (Odoo state_ids).',
    )
    zip_from                         = fields.Char(
        max_length=24, blank=True, default='', help_text='Rango de código postal, desde (Odoo zip_from).',
    )
    zip_to                            = fields.Char(
        max_length=24, blank=True, default='', help_text='Rango de código postal, hasta (Odoo zip_to).',
    )
    foreign_vat                        = fields.Char(
        max_length=32, blank=True, default='',
        help_text='RFC/VAT propio en la región mapeada por esta posición (Odoo foreign_vat).',
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
        (tax_map). Como ``original_tax_ids`` no está portado aún en
        ``AccountTax`` (ver docstring del módulo), ``tax_map`` es siempre
        vacío en este corte — el mapeo por sustitución queda declarado
        pendiente, no fabricado; el resto del método (identidad / filtro por
        universales) sí es fiel y operable.
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
        """Odoo ``_compute_tax_map`` (odoo19c: partner.py:99-105). Pendiente
        de ``AccountTax.original_tax_ids`` (ver docstring del módulo)."""
        return {}

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
