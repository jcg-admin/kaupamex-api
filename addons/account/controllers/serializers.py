"""Serializers — ``addons.account`` (registro de pago, UC-PAY-14).

Entrada de ``AccountPaymentRegisterWizard.register_payment`` (PARTE 7.1 de
``uc-pay-14-pago-parcial-abono``) + salida agregada del registro. ``account``
no declaraba capa DRF propia hasta ahora (0 ``controllers/``) — este
serializer de salida no reusa uno existente: es el primero que expone
``AccountMove`` por HTTP desde el propio addon ``account``.

Nombres de campo en inglés (convención del proyecto —
``.claude/rules/redaccion-tecnica-es.md``: "el código va en inglés"); el
mapeo a los nombres en español de la PARTE 7.1 del UC va en el
``help_text`` de cada campo.
"""
from decimal import Decimal

from rest_framework import serializers

from addons.account.models import AccountAccount, AccountJournal


class RegisterPaymentSerializer(serializers.Serializer):
    """≙ PARTE 7.1 del UC. ``difference_account_id`` es condicional a
    ``difference_handling='reconcile'`` — la condicionalidad se valida en
    ``validate()`` (EX-03), no declarando el campo requerido a secas."""

    amount = serializers.DecimalField(
        max_digits=16, decimal_places=2, min_value=Decimal('0.01'),
        help_text='Monto efectivamente recibido (odoo: amount). Puede ser '
                   'menor al saldo pendiente de la factura — PARTE 7.1 '
                   "campo 'monto'.",
    )
    journal_id = serializers.PrimaryKeyRelatedField(
        queryset=AccountJournal.objects.all(),
        help_text='Diario donde se registra el apunte del pago (odoo: '
                   "journal_id) — PARTE 7.1 campo 'diario'.",
    )
    difference_handling = serializers.ChoiceField(
        choices=['open', 'reconcile'], required=False, default='open',
        help_text="'open' deja el resto abierto; 'reconcile' lo concilia "
                   "como Write-Off en difference_account_id (odoo: "
                   "payment_difference_handling) — PARTE 7.1 campo "
                   "'manejo_diferencia'.",
    )
    difference_account_id = serializers.PrimaryKeyRelatedField(
        queryset=AccountAccount.objects.all(), required=False, allow_null=True,
        help_text='Obligatoria si difference_handling=reconcile (odoo: '
                   "writeoff_account_id) — PARTE 7.1 campo 'cuenta_diferencia'.",
    )
    difference_label = serializers.CharField(
        required=False, allow_blank=True, default='Write-Off',
        help_text='Etiqueta del apunte de diferencia; por defecto '
                   "'Write-Off' (odoo: writeoff_label) — PARTE 7.1 campo "
                   "'etiqueta_diferencia'.",
    )
    date = serializers.DateField(
        required=False, allow_null=True,
        help_text='Fecha del abono; por defecto hoy (odoo: payment_date) — '
                   "PARTE 7.1 campo 'fecha'.",
    )

    def validate(self, attrs):
        if attrs.get('difference_handling') == 'reconcile' and not attrs.get(
                'difference_account_id'):
            raise serializers.ValidationError({
                'detail': 'difference_account_id es requerido cuando '
                           'difference_handling=reconcile.',
                'codigo_error': 'DIFFERENCE_ACCOUNT_REQUIRED',
            })
        return attrs


class RegisterPaymentResultSerializer(serializers.Serializer):
    """Salida agregada del registro — no envuelve un ``AccountMove`` completo
    (fuera de alcance de este endpoint puntual; ver el docstring del
    módulo)."""

    invoice_id = serializers.IntegerField(
        help_text='La factura/asiento sobre el que se registró el abono.',
    )
    payment_move_id = serializers.IntegerField(
        help_text='El asiento del pago recién creado y publicado.',
    )
    payment_state = serializers.CharField(
        help_text="'partial' o 'paid' tras este registro (AccountMove."
                   'payment_state).',
    )
    amount_residual = serializers.DecimalField(
        max_digits=16, decimal_places=2,
        help_text='Saldo pendiente de la factura después de este abono.',
    )
    partial_reconcile_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text='Uno o dos ids — el segundo sólo si hubo Write-Off '
                   '(difference_handling=reconcile).',
    )
