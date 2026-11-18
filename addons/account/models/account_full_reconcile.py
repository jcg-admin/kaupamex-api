"""
``account.full.reconcile`` — número de conciliación total (Odoo ``account``).

Adaptación de Odoo ``addons/account/models/account_full_reconcile.py``
(odoo-tools@622ddc2a, odoo19c:, LGPL-3) — atribución y aviso de licencia
preservados (DEC-KX-03).

Sin campos propios: agrupa, vía FK inversa, los apuntes (``account.move.line
.full_reconcile``, related_name ``reconciled_line_ids``) y los partials
(``account.partial.reconcile.full_reconcile``, related_name
``partial_reconcile_ids``) que quedaron enteramente saldados — igual que la
referencia, que sólo declara ``partial_reconcile_ids``/``reconciled_line_ids``
como ``One2many`` (reversos de FK, sin columna propia).

Divergencia declarada: la referencia usa ``cr.execute_values`` (UPDATE masivo
crudo) en ``create()``/``unlink()`` para asignar/limpiar el FK en lote; aquí se
usa ``QuerySet.update()`` — mismo efecto observable, sin la optimización de
bulk SQL (no es comportamiento, es implementación; ver divergencia #5 de
``account_partial_reconcile.py``).
"""

import models
from addons.account.models.account_move_line import AccountMoveLine
from addons.base.models import TimeStampedModel
from addons.account.models.account_partial_reconcile import (
    AccountPartialReconcile,
)


class AccountFullReconcile(models.BaseModel, TimeStampedModel):
    """``account.full.reconcile`` — marca un grupo de apuntes como saldado."""

    #: Atributos de clase de ``account.full.reconcile``, verbatim
    #: (``odoo19c: account/models/account_full_reconcile.py:6-7``).
    _name = 'account.full.reconcile'
    _description = "Full Reconcile"

    class Meta:
        db_table = 'account_full_reconcile'
        ordering = ['id']
        verbose_name = 'Conciliación total'
        verbose_name_plural = 'Conciliaciones totales'

    def __str__(self) -> str:
        return f'Conciliación total #{self.pk}'

    @classmethod
    def create_from_partials(cls, partials):
        """Odoo ``create()``: agrupa un set de partials ya balanceados a cero.

        Asigna ``full_reconcile`` en las líneas y en los partials involucrados,
        y recalcula ``matching_number`` de esas líneas para que reflejen el id
        de esta conciliación total en vez de ``'P<n>'`` — mismo contrato que
        la referencia (ver ``AccountPartialReconcile._update_matching_number``,
        que lee ``full_reconcile_id`` de las líneas del grupo).
        """
        full = cls.objects.create()
        line_ids = set(partials.values_list('debit_move', flat=True)) | set(
            partials.values_list('credit_move', flat=True)
        )
        AccountMoveLine.objects.filter(pk__in=line_ids).update(
            full_reconcile=full
        )
        partials.update(full_reconcile=full)
        AccountPartialReconcile._update_matching_number(
            AccountMoveLine.objects.filter(pk__in=line_ids)
        )
        return full

    def unlink(self):
        """≙ ``unlink`` (``odoo19c: addons/account/models/
        account_full_reconcile.py:47-60``): la clave de los apuntes queda
        vacía al borrar la conciliación total, pero ``matching_number`` es un
        texto que nadie recalcula; aquí se recalcula para cada apunte que
        estaba enlazado (vacío, o ``'P<n>'`` si sobreviven parciales)."""
        line_ids = list(AccountMoveLine.objects.filter(
            full_reconcile__in=self.ids).values_list('pk', flat=True))
        res = super().unlink()
        surviving = AccountMoveLine.objects.filter(pk__in=line_ids)
        if surviving.exists():
            AccountPartialReconcile._update_matching_number(surviving)
        return res
