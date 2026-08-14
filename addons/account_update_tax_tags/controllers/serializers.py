"""Serializers — ``addons.account_update_tax_tags``.

Entrada/salida de ``AccountUpdateTaxTagsWizard.update_amls_tax_tags`` (PARTE
7.1/7.2 de ``uc-fin-11-actualizar-casillas-fiscales``).
"""
from rest_framework import serializers

from addons.base.models import ResCompany


class RecalculateTaxTagsSerializer(serializers.Serializer):
    """≙ PARTE 7.1 de ``uc-fin-11-actualizar-casillas-fiscales``.

    ``date_from`` es opcional: sin él, la vista lo calcula con
    ``AccountUpdateTaxTagsWizard.compute_date_from(company)`` — mismo default
    que ``_compute_date_from`` de la referencia.
    """

    company_id = serializers.PrimaryKeyRelatedField(
        queryset=ResCompany.objects.all(),
        help_text='La empresa sobre la que se recalcula.',
    )
    date_from = serializers.DateField(
        required=False, allow_null=True,
        help_text='Default: día siguiente al candado fiscal, u hoy si no '
                  'hay candado (compute_date_from).',
    )


class RecalculateTaxTagsResultSerializer(serializers.Serializer):
    """≙ PARTE 7.2 (caso exitoso) de ``uc-fin-11-actualizar-casillas-fiscales``."""

    date_from = serializers.DateField()
    display_lock_date_warning = serializers.BooleanField(
        help_text='True si date_from cae antes del candado fiscal '
                  '(informativo, no bloqueante).',
    )
    impacted_move_line_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text='Apuntes con fila borrada o insertada — no todo apunte '
                  'evaluado (ver PARTE 8 del UC).',
    )
