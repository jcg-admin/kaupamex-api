"""Serializers — ``addons.account_check_printing``.

Un único endpoint de acción (UC-FIN-09): sin serializer de salida propio —
la respuesta del caso exitoso hasta donde el mecanismo llega (ver
``views.py``) es un dict simple, no un recurso ``ModelSerializer``.
"""
from rest_framework import serializers

from addons.account.models import AccountPayment


class PrintPrenumberedChecksSerializer(serializers.Serializer):
    """Entrada de ``PrintPrenumberedChecksWizard.print_checks`` — ≙ PARTE 7.1
    de ``uc-fin-09-imprimir-cheques-prenumerados``.

    ``next_check_number`` no se valida aquí con un regex propio — el modelo
    ya declara esa regla (``validate_next_check_number``, única fuente de
    verdad) y la vista la ejerce contra el wizard, no la duplica.
    """

    payment_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=AccountPayment.objects.all(),
        help_text='Pagos con método "Cheques" a numerar, en el orden en que '
                  'reciben el número.',
    )
    next_check_number = serializers.CharField(
        max_length=32, allow_blank=False,
        help_text='Número inicial de la serie; sólo dígitos.',
    )
