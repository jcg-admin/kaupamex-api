"""Mixin de autorización compartido por las vistas admin de mass_mailing."""
from rest_framework.permissions import IsAuthenticated

from addons.authz.permissions import HasCapability

# Fallback neutral (nivel Kaupamex) del buzón de newsletter — ver
# website_mass_mailing.controllers.subscribe para el contexto L3/CompanySetting.
NEWSLETTER_FROM_EMAIL_DEFAULT = 'newsletter@kaupamex.com'


class _AdminOnly:
    """Autorización por capacidad (DEC-11, fail-closed): ``newsletter.edit``."""
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'newsletter.edit'
