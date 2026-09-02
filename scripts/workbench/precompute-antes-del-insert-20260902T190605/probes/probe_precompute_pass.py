"""Sonda: el pase de precompute corre y respeta el orden de dependencia."""
import django

django.setup()

from django.apps import apps  # noqa: E402

from orm.models import _precomputable_fields  # noqa: E402

SaleOrderLine = apps.get_model('sale', 'SaleOrderLine')
SaleOrder = apps.get_model('sale', 'SaleOrder')

line = SaleOrderLine(name='x')
print('explicit  ', sorted(getattr(line, '_explicit_values', None) or ()))
print('pendientes', sorted(_precomputable_fields(line)))

order = SaleOrder(validity_date=None)
print('order explicit  ', sorted(getattr(order, '_explicit_values', None) or ()))
print('order pendientes', sorted(_precomputable_fields(order)))
