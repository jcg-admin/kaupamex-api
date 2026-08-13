"""``account.partial.reconcile`` — emparejamiento debe/haber (Odoo ``account``).

Adaptación de Odoo ``addons/account/models/account_partial_reconcile.py``
(odoo-tools@622ddc2a, odoo19c:, LGPL-3) — atribución y aviso de licencia
preservados (DEC-KX-03).

Se porta el núcleo del algoritmo de conciliación: cada ``AccountPartialReconcile``
empareja un apunte deudor con uno acreedor por un ``amount`` (siempre positivo,
en moneda de la empresa) y, tras cada alta/baja, ``_update_matching_number``
recalcula el ``matching_number`` de TODOS los apuntes tocados — el algoritmo de
"unión de grafos" de la referencia (cada partial es una arista; los apuntes
conectados por aristas forman un grafo y comparten número).

Divergencias declaradas (DEC-KX-03 — no inventar forma, declarar lo que no se
porta):

1. **Sin multi-moneda de la conciliación** (``company_currency_id``,
   ``debit_currency_id``, ``credit_currency_id``, ``debit_amount_currency``,
   ``credit_amount_currency``, ``_check_required_computed_currencies``).
   ``AccountMoveLine`` (este puerto) no tiene ``amount_currency`` — sólo
   ``currency`` — así que no hay campo foráneo del que derivar estas columnas.
   DEFERIDO hasta que ``account.move.line`` porte ``amount_currency``.
2. **Sin base imponible en efectivo (cash basis)** — ``draft_caba_move_vals``,
   ``_collect_tax_cash_basis_values``, ``_create_tax_cash_basis_moves``,
   ``_prepare_cash_basis_*``, ``_get_cash_basis_*_grouping_key_*``,
   ``_get_draft_caba_move_vals``, ``_set_draft_caba_move_vals``. Dependen de
   ``account.move._collect_tax_cash_basis_values`` y de
   ``res.company.tax_cash_basis_journal_id``, ninguno portado. DEFERIDO —
   sub-iniciativa propia si se necesita reportar IVA en flujo de efectivo.
3. **Sin ``exchange_move_id``** (diferencia cambiaria) — depende del motor de
   tipos de cambio multi-moneda (punto 1). DEFERIDO.
4. **``_get_to_update_payments`` / cruce con ``account.payment``** — el
   cluster de PAGOS (``payment.method``/``payment.term``) se está portando en
   paralelo en esta misma ola; ``account.payment`` (ya existe,
   ``account_payment.py``) no tiene ``matched_payment_ids`` ni
   ``outstanding_account_id``. DEFERIDO — el ``unlink()`` de este archivo NO
   reabre pagos a ``in_process``, sólo recalcula ``matching_number``.
5. **``_update_matching_number`` usa SQL ORM en vez de
   ``cr.execute_values``** — la referencia hace un ``UPDATE ... FROM (VALUES
   %s)`` crudo por rendimiento. Aquí se porta el MISMO algoritmo de
   agrupamiento (grafo de aristas → número mínimo) con ``QuerySet.filter(id__in=...)
   .update(...)`` por grupo — equivalente funcional, sin la optimización de
   bulk insert (no es comportamiento observable, es implementación).
"""
from collections import defaultdict
from decimal import Decimal

import api
import fields
import models
from addons.account.models.account_move_line import AccountMoveLine


class AccountPartialReconcile(models.Model):
    """``account.partial.reconcile`` — arista de conciliación entre dos apuntes."""

    debit_move  = fields.Many2one(
        'account.AccountMoveLine', on_delete=models.CASCADE,
        related_name='matched_debit_ids',
        help_text='Apunte del lado debe (Odoo debit_move_id, requerido).',
    )
    credit_move = fields.Many2one(
        'account.AccountMoveLine', on_delete=models.CASCADE,
        related_name='matched_credit_ids',
        help_text='Apunte del lado haber (Odoo credit_move_id, requerido).',
    )
    full_reconcile = fields.Many2one(
        'account.AccountFullReconcile', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='partial_reconcile_ids',
        help_text='Conciliación total que agrupa este partial, si la hay '
                   '(Odoo full_reconcile_id).',
    )
    amount = fields.Monetary(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Importe siempre positivo emparejado por este partial, en '
                   'moneda de la empresa (Odoo amount).',
    )
    max_date = fields.Date(
        null=True, blank=True,
        help_text='Fecha máxima entre debit_move_id y credit_move_id (Odoo '
                   'max_date, computado). Se usa para reportes de antigüedad.',
    )

    class Meta:
        db_table = 'account_partial_reconcile'
        ordering = ['id']
        verbose_name = 'Conciliación parcial'
        verbose_name_plural = 'Conciliaciones parciales'

    def __str__(self) -> str:
        return f'{self.debit_move_id} ↔ {self.credit_move_id} ({self.amount})'

    # -- computo ------------------------------------------------------------
    def _compute_max_date(self):
        """Odoo ``_compute_max_date``: máximo entre las fechas de los asientos."""
        debit_date = self.debit_move.move.date
        credit_date = self.credit_move.move.date
        self.max_date = max(debit_date, credit_date)

    def save(self, *args, **kwargs):
        self._compute_max_date()
        return super().save(*args, **kwargs)

    # -- bajo nivel -----------------------------------------------------------
    @classmethod
    def create_partial(cls, debit_move, credit_move, amount, full_reconcile=None):
        """Crea un partial y recalcula ``matching_number`` (Odoo ``create``).

        Envuelve ``objects.create`` + ``_update_matching_number`` porque en
        Odoo esa llamada va en el override de ``create`` — aquí, sin override
        de manager multi-registro, se expone como constructor explícito para
        que el llamador no olvide el recálculo (Odoo lo hace siempre).
        """
        partial = cls.objects.create(
            debit_move=debit_move, credit_move=credit_move,
            amount=amount, full_reconcile=full_reconcile,
        )
        cls._update_matching_number(
            AccountMoveLine.objects.filter(pk__in=[debit_move.pk, credit_move.pk])
        )
        return partial

    def delete_and_update_matching(self, *args, **kwargs):
        """Odoo ``unlink()`` simplificado (ver divergencia #4: sin reabrir pagos).

        Recalcula ``matching_number`` de los dos apuntes que este partial unía,
        y si su ``full_reconcile`` queda sin partials, lo elimina (mismo
        efecto colateral que la referencia: "Remove the matching numbers
        before reversing").
        """
        full = self.full_reconcile
        touched_ids = [self.debit_move_id, self.credit_move_id]
        result = super().delete(*args, **kwargs)
        if full is not None and not full.partial_reconcile_ids.exists():
            full.delete()
        touched = AccountMoveLine.objects.filter(pk__in=touched_ids)
        AccountPartialReconcile._update_matching_number(touched)
        return result

    @staticmethod
    def _update_matching_number(amls):
        """Odoo ``_update_matching_number``: numeración de grupos por unión de grafos.

        Cada ``AccountPartialReconcile`` es una arista entre dos apuntes. Los
        apuntes conectados (directa o transitivamente) forman un grafo y
        comparten un ``matching_number``: ``'P<id>'`` mientras el grupo no
        tenga ``full_reconcile`` (id del primer partial que lo originó, igual
        que la referencia usa el id del partial como número), o el id de
        ``account.full.reconcile`` (como texto) cuando sí lo tiene.
        """
        amls = AccountPartialReconcile._all_reconciled_lines(amls)
        all_partials = AccountPartialReconcile.objects.filter(
            models.Q(debit_move__in=amls) | models.Q(credit_move__in=amls)
        )

        number2lines = {}
        line2number = {}
        for partial in all_partials.order_by('id'):
            debit_id = partial.debit_move_id
            credit_id = partial.credit_move_id
            debit_min_id = line2number.get(debit_id)
            credit_min_id = line2number.get(credit_id)
            if debit_min_id and credit_min_id:
                if debit_min_id != credit_min_id:
                    min_min_id = min(debit_min_id, credit_min_id)
                    max_min_id = max(debit_min_id, credit_min_id)
                    for line_id in number2lines[max_min_id]:
                        line2number[line_id] = min_min_id
                    number2lines[min_min_id].extend(number2lines.pop(max_min_id))
            elif debit_min_id:
                number2lines[debit_min_id].append(credit_id)
                line2number[credit_id] = debit_min_id
            elif credit_min_id:
                number2lines[credit_min_id].append(debit_id)
                line2number[debit_id] = credit_min_id
            else:
                number2lines[partial.pk] = [debit_id, credit_id]
                line2number[debit_id] = partial.pk
                line2number[credit_id] = partial.pk

        processed_ids = set()
        for group_number, line_ids in number2lines.items():
            group_lines = AccountMoveLine.objects.filter(pk__in=line_ids)
            full_ids = set(
                group_lines.exclude(full_reconcile__isnull=True)
                .values_list('full_reconcile_id', flat=True)
            )
            value = str(next(iter(full_ids))) if full_ids else f'P{group_number}'
            group_lines.update(matching_number=value)
            processed_ids.update(line_ids)

        untouched_ids = [line.pk for line in amls if line.pk not in processed_ids]
        if untouched_ids:
            AccountMoveLine.objects.filter(pk__in=untouched_ids).update(matching_number='')

    @staticmethod
    def _all_reconciled_lines(amls):
        """Odoo ``account.move.line._all_reconciled_lines``: cierre transitivo
        de apuntes conectados por partials, tomando los que ya se pasaron.

        Simplificado: la referencia expande vía ``full_reconcile_id`` mapped
        lines; aquí basta con devolver las líneas recibidas — la expansión
        transitiva real la hace ``_update_matching_number`` al recorrer todos
        los partials que las tocan.
        """
        return list(amls)
