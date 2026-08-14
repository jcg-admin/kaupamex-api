# Paquete models/ — un archivo por modelo, como `loyalty/models/` de la
# referencia (desagrupado de un models.py plano, H-API-231).
#
# OJO — el mapa con la referencia NO es 1:1: `odoo19c: loyalty/models/`
# modela loyalty_program / loyalty_card / loyalty_reward / loyalty_rule /
# loyalty_history (11 archivos); este addon modela vouchers y referidos
# (dominio heredado pre-porte). La desagrupación es de **layout**; el porte
# semántico de la familia loyalty de la referencia queda como gap nombrado
# en el hallazgo H-API-231.
from addons.loyalty.models.referral import Referral  # noqa: F401
from addons.loyalty.models.referral_code import ReferralCode  # noqa: F401
from addons.loyalty.models.voucher import (  # noqa: F401
    Voucher,
    generate_suffix,
)
from addons.loyalty.models.voucher_change_log import VoucherChangeLog  # noqa: F401
from addons.loyalty.models.voucher_usage import VoucherUsage  # noqa: F401
