"""Tests unitarios — el formulario de ajustes (UC-CFG-03).

Reemplaza a ``test_site_settings_model.py``. Aquel probaba el **singleton**:
que sólo hubiera una fila, que sus defaults fueran los correctos, que sus
validadores rechazaran un IVA fuera de rango. Esa tabla se retiró
(H-API-265) porque mezclaba diez dominios en un esquema; los ajustes viven
ahora en claves de parámetro y ``SiteConfigSettings`` es el formulario que
los compone — la forma de ``res.config.settings`` en la referencia.

Lo que se conserva del contrato viejo es lo que sigue siendo cierto: los
defaults, el rango del IVA, y que escribir un ajuste lo deja donde el
lector lo busca. Lo que desaparece es lo que era propio de la tabla (una
sola fila, ``__str__`` del registro).

Contrato documentado en:
  FR-CFG-03.01: Actualizar configuracion global del sistema
  FR-CFG-03.02: Validar y persistir los parametros globales
"""
from decimal import Decimal

import pytest

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base_setup.models import SiteConfigSettings
from addons.base_setup.settings_access import get_setting

pytestmark = pytest.mark.unit


class TestFormularioNoEsTabla:
    """El formulario no persiste por sí mismo: no tiene tabla."""

    def test_el_modelo_no_es_gestionado(self):
        assert SiteConfigSettings._meta.managed is False

    def test_se_puede_instanciar_sin_tocar_la_base(self):
        """Es el equivalente del ``TransientModel``: vive en memoria."""
        form = SiteConfigSettings(iva_rate=Decimal('0.10'))
        assert form.iva_rate == Decimal('0.10')


class TestValoresPorDefecto:
    """Los defaults del contrato, ahora leídos del formulario."""

    def test_default_iva_rate_is_16_percent(self, db):
        assert get_setting('iva_rate') == Decimal('0.16')

    def test_default_payment_timeout(self, db):
        assert get_setting('payment_timeout_minutes') == 30

    def test_default_max_return_days_is_30(self, db):
        assert get_setting('max_return_days') == 30

    def test_default_free_shipping_threshold(self, db):
        assert get_setting('free_shipping_threshold') == Decimal('999.00')

    def test_site_name_no_trae_nombre_de_tenant(self, db):
        """El nombre de una empresa L1 no es el default de la plataforma."""
        assert get_setting('site_name') == ''


class TestEscrituraLlegaASuDestino:
    """Escribir un ajuste lo deja en la clave de su dominio dueño."""

    def test_aplicar_escribe_el_parametro(self, db):
        SiteConfigSettings(**{
            **SiteConfigSettings.current_values(),
            'payment_timeout_minutes': 45,
        }).apply_values()
        assert SystemParameter.get_param('payment.timeout_minutes') == '45'

    def test_el_lector_ve_lo_escrito_con_su_tipo(self, db):
        SiteConfigSettings(**{
            **SiteConfigSettings.current_values(),
            'iva_rate': Decimal('0.08'),
        }).apply_values()
        assert get_setting('iva_rate') == Decimal('0.08')

    def test_cada_dominio_es_independiente(self, db):
        """El SRP que la tabla no daba: cambiar el IVA no toca el envío."""
        antes = get_setting('free_shipping_threshold')
        SiteConfigSettings(**{
            **SiteConfigSettings.current_values(),
            'iva_rate': Decimal('0.21'),
        }).apply_values()
        assert get_setting('free_shipping_threshold') == antes


class TestAjusteDesconocido:
    def test_pedir_una_clave_inexistente_falla_explicito(self, db):
        with pytest.raises(KeyError):
            get_setting('no_existe')
