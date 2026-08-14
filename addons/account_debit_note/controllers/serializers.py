"""Serializers — ``addons.account_debit_note``.

Entrada de ``AccountDebitNoteWizard.create_debit`` (PARTE 7.1 de
``uc-fin-10-crear-nota-de-debito``) + salida mínima de las notas de débito
creadas — ``account`` no declara su propia capa DRF (0 ``controllers/`` en
ese addon, H-API-406), así que este serializer de salida no reusa uno
existente: es el primero que expone ``AccountMove`` por HTTP.
"""
from rest_framework import serializers

from addons.account.models import AccountJournal, AccountMove


class CreateDebitNoteSerializer(serializers.Serializer):
    """≙ PARTE 7.1 de ``uc-fin-10-crear-nota-de-debito``. Los cuatro campos
    opcionales caen a los defaults que ``prepare_default_values`` calcula
    del movimiento de origen cuando el llamador no los provee."""

    move_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=AccountMove.objects.all(),
        help_text='Movimientos de origen (deben estar posted).',
    )
    date = serializers.DateField(
        required=False, allow_null=True,
        help_text='Default: la fecha del movimiento original.',
    )
    reason = serializers.CharField(
        required=False, allow_blank=True, allow_null=True,
        help_text='Se agrega a la referencia del nuevo movimiento.',
    )
    journal_id = serializers.PrimaryKeyRelatedField(
        required=False, allow_null=True, queryset=AccountJournal.objects.all(),
        help_text='Default: el diario del movimiento original.',
    )
    copy_lines = serializers.BooleanField(
        required=False, default=False,
        help_text='Si es true, copia las líneas del movimiento original.',
    )


class DebitNoteResultSerializer(serializers.ModelSerializer):
    """La nota de débito creada — salida mínima (id + los campos que
    ``prepare_default_values`` fija), no un ``AccountMove`` API completo
    (fuera de alcance, ver el docstring del módulo)."""

    class Meta:
        model = AccountMove
        fields = ['id', 'name', 'ref', 'date', 'state', 'move_type',
                  'journal', 'partner', 'currency', 'company']
        read_only_fields = fields
