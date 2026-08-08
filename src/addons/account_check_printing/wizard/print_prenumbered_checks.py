"""``print.prenumbered.checks`` — el asistente "Imprimir cheques prenumerados".

Adaptación de ``odoo19c: addons/account_check_printing/wizard/
print_prenumbered_checks.py`` (``odoo-tools@622ddc2a``, LGPL-3 — atribución y
aviso de licencia preservados, DEC-KX-03).

``TransientModel`` → clase con classmethods, no tabla
==========================================================

Mismo criterio que ``account_debit_note.AccountDebitNoteWizard`` y
``base_setup.SiteConfigSettings``: "formulario, no tabla". El estado del
wizard (qué pagos, qué número inicial) lo pasa el llamador como parámetros
de los classmethods, en vez de vivir en una fila.

Los tres símbolos de la referencia se portan
=================================================

===========================  ==========================================
Símbolo de la referencia       Qué pasa aquí
===========================  ==========================================
``next_check_number`` (campo)  PORTADO — parámetro ``next_check_number``
``_check_next_check_number``   PORTADO — ``validate_next_check_number()``
``print_checks``               PORTADO — ``print_checks()``
===========================  ==========================================

Divergencia declarada — sin ``action_post``/``do_print_checks`` completos
================================================================================

La referencia postea los pagos en borrador (``action_post()``) y luego
delega el render en ``do_print_checks()``. Ninguno de los dos existe
completo en este árbol (ver ``models/account_payment.py``, Divergencia 6 y
7 de ese docstring): aquí se escribe el estado ``in_process`` directamente
(mismo criterio que ``CheckPrintingPaymentInfo.prepare_print_checks``) y el
render final delega en ``CheckPrintingPaymentInfo.render_checks``, que
declara su propio bloqueo (sin motor de reportes en el árbol).

``close_on_report_download`` (``odoo19c: :31``) no se porta — es una
instrucción para el cliente web de Odoo (cerrar el wizard al terminar la
descarga), sin análogo en un backend headless.
"""
import re

from exceptions import ValidationError
from orm.models_transient import TransientModel
from tools.translate import _
from addons.account_check_printing.models.account_payment import CheckPrintingPaymentInfo


class PrintPrenumberedChecksWizard(TransientModel):
    """Asistente "Imprimir cheques prenumerados" — ≙ ``print.prenumbered.checks``.

    Sin tabla (``TransientModel``, ``managed = False``): el estado del
    wizard lo pasa el llamador como argumentos de los classmethods.
    """

    class Meta:
        abstract = True
        managed = False

    @classmethod
    def validate_next_check_number(cls, value):
        """≙ ``_check_next_check_number``
        (``odoo19c: print_prenumbered_checks.py:15-19``): sólo dígitos."""
        if value and not re.match(r'^[0-9]+$', value):
            raise ValidationError(_('Next Check Number should only contains numbers.'))
        return value

    @classmethod
    def print_checks(cls, payments, next_check_number):
        """≙ ``print_checks`` (``odoo19c: print_prenumbered_checks.py:21-32``).

        Postea los pagos en borrador, numera secuencialmente en el orden
        recibido comenzando en ``next_check_number``, marca los pagos como
        enviados (validando el diseño de cheque) y delega el render final.
        """
        cls.validate_next_check_number(next_check_number)
        check_number = int(next_check_number)
        number_len = len(next_check_number or '')

        for payment in payments:
            if payment.state == 'draft':
                payment.state = 'in_process'
                payment.save(update_fields=['state'])

        for payment in payments:
            row = CheckPrintingPaymentInfo.for_payment(payment, create=True)
            row.check_number = '%0{}d'.format(number_len) % check_number
            row.save(update_fields=['check_number', 'updated_at'])
            CheckPrintingPaymentInfo.validate_check_number_uniqueness(payment)
            check_number += 1

        CheckPrintingPaymentInfo.mark_as_sent(payments)
        return CheckPrintingPaymentInfo.render_checks(payments)
