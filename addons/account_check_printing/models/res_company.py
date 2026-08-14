"""``res.company`` — lo que ``account_check_printing`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/account_check_printing/models/res_company.py``
(``odoo-tools@622ddc2a``, LGPL-3 — atribución y aviso de licencia
preservados, DEC-KX-03). Seis campos, todos portados:
``account_check_printing_layout``, ``account_check_printing_date_label``,
``account_check_printing_multi_stub``, ``account_check_printing_margin_top``,
``account_check_printing_margin_left``, ``account_check_printing_margin_right``.

Cross-app ``_inherit`` → RELATED OneToOne (DEC-SALE-01, mismo criterio que
``account_add_gln.PartnerGln`` / ``account_debit_note.JournalDebitSequence``):
Django no inyecta una columna en la tabla de OTRO addon sin migrar la app
dueña (``res.company`` vive en ``base`` en este árbol), así que
``CheckPrintingCompanySettings`` cuelga de ``base.ResCompany`` con su propia
tabla — sin tocar ``base`` ni su migración.

``account_check_printing_layout`` — selection dinámico, hoy con una sola opción
====================================================================================

La referencia declara el campo con **un** valor base
(``[('disabled', 'None')]``, ``odoo19c: res_company.py:13-15``) y un
comentario explícito: *"needs to be overridden with `selection_add` in the
modules which intends to add report layouts"* — cada país-layout
(``l10n_us_check_printing``, etc.) amplía el selection. Ninguno está portado
en este árbol (``find src/addons -iname "*check_layout*" -o -iname
"*check_printing*"`` → sólo este addon [PROVEN]), así que
``LAYOUT_CHOICES`` tiene hoy una sola opción real: "Ninguno". Es fiel a la
referencia, no una limitación de este puerto — el mismo comentario de
``selection_add`` sigue siendo la vía de extensión el día que se porte un
diseño de talón concreto.
"""
import fields
import models
from addons.base.models import ResCompany, TimeStampedModel


class CheckPrintingCompanySettings(TimeStampedModel):
    """Ajustes de impresión de cheques de una empresa — ≙ los 6 campos
    ``account_check_printing_*`` de ``res.company``."""

    #: ≙ la selección base de la referencia (``res_company.py:13-15``). Ver
    #: la sección "selection dinámico" del docstring del módulo.
    LAYOUT_CHOICES = [('disabled', 'Ninguno')]

    company = models.OneToOneField(
        ResCompany, on_delete=models.CASCADE,
        related_name='check_printing_settings',
        help_text='Empresa (Odoo _inherit res.company).',
    )
    layout = fields.Selection(
        max_length=64, choices=LAYOUT_CHOICES, default='disabled',
        verbose_name='Diseño de cheque',
        help_text='Formato del papel donde se imprimen los cheques. '
                  '"Ninguno" desactiva la impresión (Odoo '
                  'account_check_printing_layout).',
    )
    date_label = fields.Boolean(
        default=True, verbose_name='Imprimir etiqueta de fecha',
        help_text='Imprime la etiqueta de fecha según CPA. Desactivar si el '
                  'talonario preimpreso ya la trae (Odoo '
                  'account_check_printing_date_label).',
    )
    multi_stub = fields.Boolean(
        default=False, verbose_name='Talón de cheque en varias páginas',
        help_text='Permite que el detalle del talón use varias páginas si '
                  'no cabe en una sola (Odoo account_check_printing_multi_stub).',
    )
    margin_top = fields.Float(
        default=0.25, verbose_name='Margen superior',
        help_text='Ajusta el margen del cheque generado, en pulgadas '
                  '(Odoo account_check_printing_margin_top).',
    )
    margin_left = fields.Float(
        default=0.25, verbose_name='Margen izquierdo',
        help_text='Odoo account_check_printing_margin_left.',
    )
    margin_right = fields.Float(
        default=0.25, verbose_name='Margen derecho',
        help_text='Odoo account_check_printing_margin_right.',
    )

    class Meta:
        db_table = 'account_check_printing_company_settings'
        verbose_name = 'Ajustes de impresión de cheques (empresa)'
        verbose_name_plural = 'Ajustes de impresión de cheques (empresas)'

    def __str__(self) -> str:
        return f'Cheques — {self.company} ({self.get_layout_display()})'

    # -- lectores usados por account_journal.py / account_payment.py -------

    @classmethod
    def layout_for(cls, company):
        """Diseño de cheque efectivo de ``company`` — la fila si existe, o
        el default del campo si nunca se creó (≙ Odoo ``default='disabled'``
        cuando el registro de la empresa aún no tiene override)."""
        if company is None:
            return 'disabled'
        row = cls.objects.filter(company=company).first()
        return row.layout if row else 'disabled'

    @classmethod
    def get_or_create_for(cls, company):
        row, _created = cls.objects.get_or_create(company=company)
        return row

    @classmethod
    def available_layouts(cls):
        """Opciones de diseño EXCLUYENDO "disabled" — ≙
        ``_get_check_printing_layouts`` (``odoo19c: account_journal.py:43-46``,
        que en la referencia vive en el diario y lee el selection de la
        empresa; aquí se expone donde vive el dato)."""
        return [(value, label) for value, label in cls.LAYOUT_CHOICES if value != 'disabled']

    @classmethod
    def check_layout_available(cls):
        """¿Hay más de un diseño para elegir? — ≙
        ``check_layout_available`` de ``account.payment``
        (``odoo19c: account_payment.py:33-37``): ``len(selection) > 1``.
        Hoy es siempre ``False`` — ver la sección "selection dinámico" del
        docstring del módulo."""
        return len(cls.LAYOUT_CHOICES) > 1
