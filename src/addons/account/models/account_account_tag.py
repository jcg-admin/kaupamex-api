"""``account.account.tag`` — casilla fiscal (Odoo ``account``).

Adaptación de Odoo addons/account/models/account_account_tag.py
(odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de, odoo19c:, LGPL-3).

Etiqueta reutilizable sobre cuentas/impuestos/productos — la unidad que
``account.tax.repartition.line.tag_ids`` reparte hacia los reportes fiscales
("casillas" del IVA). Es el segundo prerrequisito (junto con
``account.tax.repartition.line``) de ``account_update_tax_tags``.

Campos núcleo portados: ``name``, ``applicability``, ``color``, ``active``,
``country``. Único ``(name, applicability, country)`` (Odoo ``_name_uniq``).

Las **tres etiquetas maestras** del estado de flujo de efectivo
(``account_tag_operating``/``_financing``/``_investing``) las siembra
``migrations/0012_seed_account_tags.py``; su especificación vive en
``data/account_tags.py``.

NO se porta: ``report_expression_id``/``balance_negate`` (computados vía SQL
crudo contra ``account.report.expression`` — el motor de reportes fiscales
no está portado; declarado, no fabricado) ni ``_translate_tax_tags``/
``_compute_display_name`` con ``multi_vat_foreign_country_ids`` (i18n +
multi-VAT del cliente web, sin análogo en DRF).

**Corregido 2026-08-06:** este docstring declaraba
``_unlink_except_master_tags`` fuera del porte porque *"protege 3 tags XML-ID
de datos de demo que este proyecto no carga"*. Las dos mitades eran falsas: no
son datos de demo (viven en ``data/account_data.xml``, que la referencia carga
siempre) y sí se cargan aquí desde la migración anterior. La guarda se porta
abajo. Ver :ref:`h-api-352`.
"""
import fields
import models
from addons.base.models.ir_model import IrModelData
from exceptions import UserError
from tools.translate import _


class AccountAccountTag(models.Model):
    """``account.account.tag`` — etiqueta de cuenta/impuesto/producto."""

    APPLICABILITIES = [
        ('accounts', 'Cuentas'),
        ('taxes', 'Impuestos'),
        ('products', 'Productos'),
    ]

    name           = fields.Char(
        max_length=255, help_text='Nombre de la etiqueta (Odoo name, requerido).',
    )
    applicability   = fields.Selection(
        max_length=8, choices=APPLICABILITIES, default='accounts',
        help_text='Dónde aplica la etiqueta (Odoo applicability, requerido).',
    )
    color            = fields.Integer(
        default=0, help_text='Índice de color en UI (Odoo color).',
    )
    active            = fields.Boolean(
        default=True, help_text='Etiqueta activa; desactivar en vez de borrar (Odoo active).',
    )
    country            = fields.Many2one(
        'base.ResCountry', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='account_tags',
        help_text='País donde aplica, cuando applicability=taxes (Odoo country_id).',
    )

    class Meta:
        db_table = 'account_account_tag'
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'applicability', 'country'],
                name='unique_account_tag_name_applicability_country',
            ),
        ]
        verbose_name = 'Casilla fiscal'
        verbose_name_plural = 'Casillas fiscales'

    def __str__(self) -> str:
        return self.name

    #: Identificadores externos que el plan contable cita; borrarlos lo rompe.
    MASTER_XMLIDS = (
        'account.account_tag_operating',
        'account.account_tag_financing',
        'account.account_tag_investing',
    )

    def delete(self, *args, **kwargs):
        """Impide borrar una etiqueta maestra — ≙ ``_unlink_except_master_tags``.

        ≙ ``odoo19c: account_account_tag.py:110-120`` (``odoo-tools@622ddc2a``).
        Allá la guarda cuelga de ``@api.ondelete``; aquí del ``delete`` del
        modelo, que es el punto equivalente en este stack.

        No es una protección decorativa: el CSV del plan genérico cita las tres
        por identificador externo, y ``get_accounts_data_values`` etiqueta con
        ``account_tag_investing`` las dos cuentas de diferencia de efectivo.
        Borrar una deja al plan sin resolver esa columna.
        """
        for xmlid in self.MASTER_XMLIDS:
            master = IrModelData.ref(xmlid, raise_if_not_found=False)
            if master is not None and master.pk == self.pk:
                raise UserError(
                    _('No se puede borrar la etiqueta «%(name)s»: la usa la '
                      'definición del plan contable.') % {'name': self.name})
        return super().delete(*args, **kwargs)
