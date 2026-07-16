"""
Tests — estimación de fecha de entrega "Recíbelo" (G-ENV-02 / EP-01).

Regla DEC-ENV-03: ventana de días hábiles de la zona + corte 11:00 local +
sin domingo. Se pasa ``now`` explícito (aware, UTC) para fijar el escenario.
"""
import pytest
from datetime import datetime, date, timezone as dt_tz

from apps.addons.orders.delivery import (
    estimate_delivery_window, delivery_estimate_dict, _add_business_days,
)

pytestmark = pytest.mark.integration


class _Zone:
    """Doble ligero de ShippingZone (la util sólo lee estimated_days_*)."""
    def __init__(self, lo, hi):
        self.estimated_days_min = lo
        self.estimated_days_max = hi


# America/Mexico_City = UTC-6 (sin DST desde 2022). 09:00 local = 15:00 UTC.
def _utc(y, m, d, h):
    return datetime(y, m, d, h, 0, tzinfo=dt_tz.utc)


class TestAddBusinessDays:
    def test_salta_domingo(self):
        # 2026-07-11 es sábado; +1 día hábil salta el domingo 12 → lunes 13.
        assert _add_business_days(date(2026, 7, 11), 1) == date(2026, 7, 13)

    def test_cero_normaliza_domingo_a_lunes(self):
        assert _add_business_days(date(2026, 7, 12), 0) == date(2026, 7, 13)  # dom→lun
        assert _add_business_days(date(2026, 7, 13), 0) == date(2026, 7, 13)  # lun queda


class TestEstimateWindow:
    def test_antes_del_corte_cuenta_desde_hoy(self):
        # Miércoles 2026-07-08, 09:00 local (15:00 UTC) < 11:00 → base = hoy.
        zone = _Zone(1, 3)
        lo, hi = estimate_delivery_window(zone, now=_utc(2026, 7, 8, 15))
        assert lo == date(2026, 7, 9)   # +1 hábil
        assert hi == date(2026, 7, 11)  # +3 hábiles (jue, vie, sáb)

    def test_despues_del_corte_base_es_siguiente_dia_habil(self):
        # Miércoles 2026-07-08, 12:00 local (18:00 UTC) >= 11:00 → base = jueves 9.
        zone = _Zone(1, 1)
        lo, hi = estimate_delivery_window(zone, now=_utc(2026, 7, 8, 18))
        assert lo == hi == date(2026, 7, 10)  # base jueves + 1 hábil = viernes 10

    def test_nunca_entrega_en_domingo(self):
        # Sábado 2026-07-11, 09:00 local, min=1 → domingo 12 se salta → lunes 13.
        zone = _Zone(1, 1)
        lo, hi = estimate_delivery_window(zone, now=_utc(2026, 7, 11, 15))
        assert lo.weekday() != 6 and hi.weekday() != 6
        assert lo == date(2026, 7, 13)

    def test_zona_sin_ventana_devuelve_none(self):
        assert estimate_delivery_window(_Zone(None, None)) == (None, None)

    def test_solo_max_usa_max_para_ambos(self):
        zone = _Zone(None, 2)
        lo, hi = estimate_delivery_window(zone, now=_utc(2026, 7, 8, 15))
        assert lo == hi  # lo cae a max cuando min es None


class TestEstimateDict:
    def test_dict_shape_y_same_day(self):
        d = delivery_estimate_dict(_Zone(1, 1), now=_utc(2026, 7, 8, 15))
        assert set(d) == {'from', 'to', 'same_day'}
        assert d['same_day'] is True
        assert d['from'] == d['to'] == '2026-07-09'

    def test_dict_none_sin_ventana(self):
        assert delivery_estimate_dict(_Zone(None, None)) is None
