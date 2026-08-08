"""Contrato de la extensión de ``_get_payment_method_information`` — ≙
``account.payment.method._inherit`` de la referencia (ver
``models/account_payment_method.py``). H-API-364: ``chain_method`` con
``combine=``, nunca ``hasattr`` — este test verifica precisamente que el
caso base (``manual``) sobrevive a la cadena.
"""
from addons.account.models import AccountPaymentMethod
from addons.account_check_printing.models.account_payment_method import (
    apply_account_check_printing_payment_method_extensions,
)

apply_account_check_printing_payment_method_extensions()


class TestPaymentMethodInformation:
    def test_check_printing_is_present(self):
        info = AccountPaymentMethod()._get_payment_method_information()
        assert info['check_printing'] == {'mode': 'multi', 'type': ('bank',)}

    def test_manual_from_the_base_class_survives_the_chain(self):
        info = AccountPaymentMethod()._get_payment_method_information()
        assert info['manual'] == {'mode': 'multi', 'type': ('bank', 'cash', 'credit')}

    def test_reapplying_does_not_lose_either_entry(self):
        # ``chain_method`` es idempotente (``_already_in_chain``) — reaplicar
        # no debe duplicar el envoltorio ni perder el caso base.
        apply_account_check_printing_payment_method_extensions()
        info = AccountPaymentMethod()._get_payment_method_information()
        # Se afirma PRESENCIA, nunca exclusividad. La versión anterior exigía
        # `set(info) == {'manual', 'check_printing'}` y pasaba sólo porque
        # `account_payment` no estaba en INSTALLED_APPS; al cablearlo, ese
        # addon suma sus pasarelas a la MISMA cadena (`chain_method` con
        # `combine`) y la igualdad se rompía — sin que nada estuviera mal.
        # Un assert de exclusividad sobre un hook acumulativo miente en cuanto
        # se activa el addon hermano.
        assert info['check_printing'] == {'mode': 'multi', 'type': ('bank',)}
        assert info['manual'] == {'mode': 'multi', 'type': ('bank', 'cash', 'credit')}
