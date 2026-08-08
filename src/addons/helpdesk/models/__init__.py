"""Models — ``addons.helpdesk``.

Layout ``models/`` con un archivo por modelo, espejo de la referencia
(``odoo19e: helpdesk/models/``; ``odoo18e:`` idéntico salvo ``populate/``, que
19 no trae y por tanto no se adopta — 19 gobierna). Este ``__init__``
re-exporta la superficie pública: ``from addons.helpdesk.models import
SupportTicket`` sigue siendo la forma de importar, igual que antes.
"""
from addons.helpdesk.models.support_ticket import SupportTicket
from addons.helpdesk.models.support_ticket_reply import SupportTicketReply

__all__ = ['SupportTicket', 'SupportTicketReply']
