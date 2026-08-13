"""Serializers — ``addons.account_test``."""
from rest_framework import serializers

from addons.account_test.models.accounting_assert_test import AccountingAssertTest


class AccountingAssertTestSerializer(serializers.ModelSerializer):
    """``accounting.assert.test`` — colección/detalle.

    ``Meta.fields`` explícito (nunca ``'__all__'``, ver
    ``references/serializers.md`` del skill ``backend-drf``): expone los
    cinco campos de la referencia + el ``id``.
    """

    class Meta:
        model = AccountingAssertTest
        fields = ['id', 'name', 'desc', 'code_exec', 'active', 'sequence']


class AccountingAssertTestRunResultSerializer(serializers.Serializer):
    """Respuesta de ``POST .../run/`` — no es un ``ModelSerializer`` porque
    no hay columna que respalde ``passed``/``result`` (son el resultado de
    la ejecución, no del registro). ≙ el contexto que
    ``_get_report_values`` arma para la plantilla QWeb de la referencia,
    aplanado a JSON — ver la sección "``report`` → ``controllers``" del
    docstring de ``models/accounting_assert_test.py``.
    """

    id = serializers.IntegerField()
    name = serializers.CharField()
    passed = serializers.BooleanField(
        help_text='True si `result` vino vacío tras ejecutar `code_exec` '
                  '(≙ el mensaje de éxito por defecto de la referencia).',
    )
    result = serializers.ListField(
        child=serializers.CharField(),
        help_text='Una línea por fila de `result` — formateada igual que '
                  '`_execute_code` de la referencia.',
    )
