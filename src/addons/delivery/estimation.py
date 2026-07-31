"""Estimación de fecha de entrega ("Recíbelo <rango>") — G-ENV-02 / EP-01.

Regla de negocio (DEC-ENV-03):

- La ventana de días de una zona es ``ShippingZone.estimated_days_min/max``
  (días **hábiles**).
- **Corte (cutoff) 11:00** (hora local America/Mexico_City): los pedidos
  confirmados antes de las 11:00 cuentan desde hoy; a partir de las 11:00 la
  base es el siguiente día hábil (regla del banner "recolección diaria 11:00").
- **Sin domingo:** el conteo de días hábiles excluye domingo, así que la fecha
  de entrega nunca cae en domingo. (Feriados MX quedan como deuda: v1 sólo
  excluye domingo — ver plan-tareas-entrega-y-pickup, riesgo Baja.)

La función es pura salvo por ``timezone.now()`` cuando ``now`` es None; para
tests, pasar un ``now`` explícito.
"""
from datetime import date, timedelta

from django.utils import timezone

DELIVERY_CUTOFF_HOUR = 11  # 11:00 local; configurable a futuro vía SiteSettings
_SUNDAY = 6  # date.weekday(): lunes=0 … domingo=6


def _add_business_days(start: date, n: int) -> date:
    """Devuelve la fecha ``n`` días hábiles después de ``start``, saltando
    domingos. ``n`` >= 1; con ``n`` == 0 devuelve ``start`` (o el siguiente día
    hábil si ``start`` cae en domingo)."""
    d = start
    if n <= 0:
        # Normaliza: nunca devolver un domingo.
        return d + timedelta(days=1) if d.weekday() == _SUNDAY else d
    added = 0
    while added < n:
        d += timedelta(days=1)
        if d.weekday() != _SUNDAY:
            added += 1
    return d


def estimate_delivery_window(zone, now=None, cutoff_hour=DELIVERY_CUTOFF_HOUR):
    """(date_min, date_max) de entrega para ``zone`` dado ``now``.

    Devuelve ``(None, None)`` si la zona no tiene ventana de días definida.
    """
    days_min = getattr(zone, 'estimated_days_min', None)
    days_max = getattr(zone, 'estimated_days_max', None)
    if not days_min and not days_max:
        return (None, None)
    lo = days_min or days_max
    hi = days_max or days_min

    now = now or timezone.now()
    local = timezone.localtime(now)
    base = local.date()
    # A partir del corte, la base es el siguiente día hábil.
    if local.hour >= cutoff_hour:
        base = _add_business_days(base, 1)

    date_min = _add_business_days(base, lo)
    date_max = _add_business_days(base, hi)
    return (date_min, date_max)


def delivery_estimate_dict(zone, now=None):
    """Proyección serializable de la ventana de entrega para el storefront.

    ``{'from': 'YYYY-MM-DD', 'to': 'YYYY-MM-DD', 'same_day': bool}`` o None si la
    zona no tiene ventana. El etiquetado ("Recíbelo el 10–14 jul") se hace en el
    front (i18n)."""
    date_min, date_max = estimate_delivery_window(zone, now=now)
    if date_min is None:
        return None
    return {
        'from': date_min.isoformat(),
        'to': date_max.isoformat(),
        'same_day': date_min == date_max,
    }
