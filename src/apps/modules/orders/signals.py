"""
Signals — apps.modules.orders. DEC-BC-19.

order_created: emitida al finalizar un checkout exitoso.
Los handlers downstream (notifications, analytics) se conectan
en sus propios apps.py usando receiver().
"""
from django.dispatch import Signal

order_created = Signal()
