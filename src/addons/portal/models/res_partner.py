"""Reglas de edición del partner por un usuario de portal / público.

Adaptación fiel de Odoo ``portal/models/res_partner.py`` (LGPL-3, 55 loc,
leído completo). La referencia extiende ``res.partner`` con ``_inherit``;
Django no permite inyectar métodos en el modelo de otra app, así que son
funciones sobre el partner (mismo criterio que ``authz_ldap.res_users``).

- ``_get_frontend_writable_fields`` → ``frontend_writable_fields()``: el
  allowlist de campos que un usuario de portal/público puede cambiar en su
  contacto (nunca campo libre — ver ``backend-drf/filtering``).
- ``can_edit_vat`` / ``_can_edit_country`` → ``can_edit_vat(partner)`` /
  ``can_edit_country(partner)``.
- ``_can_be_edited_by_current_customer`` → ``can_be_edited_by(partner,
  user)``: el partner es editable si es el del usuario o un hijo de su
  entidad comercial con tipo dirección.
- ``_get_current_partner`` → ``current_partner(user)``: el partner del
  usuario, o vacío si es público (usa ``ResUsers.is_public()``, el eje real
  portado en H-API-234).
- ``_get_delivery_address_domain`` → NO portado: arma un ``Domain`` de Odoo
  para el selector de direcciones de envío del checkout QWeb; el filtrado de
  direcciones del SPA lo resuelve su propio endpoint.
"""


def frontend_writable_fields():
    """≙ ``_get_frontend_writable_fields`` (res_partner.py:10-19)."""
    return {
        'name', 'phone', 'email', 'street', 'street2', 'city', 'state_id',
        'country_id', 'zip', 'zipcode', 'vat', 'company_name',
    }


def can_edit_country(partner):
    """≙ ``_can_edit_country`` (res_partner.py:21-23)."""
    return True


def can_edit_vat(partner):
    """≙ ``can_edit_vat`` (res_partner.py:25-30): sólo la entidad comercial
    (el partner sin padre) edita el ``vat`` — se sincroniza a los hijos."""
    return partner.parent_id is None


def current_partner(user):
    """≙ ``_get_current_partner`` (res_partner.py:44-49): el partner del
    usuario, o ``None`` si es público."""
    if user.is_public():
        return None
    return user.partner


def can_be_edited_by(partner, user):
    """≙ ``_can_be_edited_by_current_customer`` (res_partner.py:32-42).

    Editable si es el partner del usuario, o un hijo (``child_of``) de su
    entidad comercial con tipo de dirección (invoice/delivery/other).
    """
    current = current_partner(user)
    if current is None:
        return False
    if partner.pk == current.pk:
        return True
    commercial = _commercial_partner(current)
    return (
        partner.type in ('invoice', 'delivery', 'other')
        and _is_child_of(partner, commercial)
    )


def _commercial_partner(partner):
    """La entidad comercial: el ancestro raíz de la jerarquía de partners
    (≙ ``commercial_partner_id`` de la referencia)."""
    node = partner
    while node.parent_id is not None:
        node = node.parent
    return node


def _is_child_of(partner, ancestor):
    """True si ``partner`` es ``ancestor`` o un descendiente suyo
    (≙ el operador ``child_of`` de Odoo sobre la jerarquía de partners)."""
    node = partner
    while node is not None:
        if node.pk == ancestor.pk:
            return True
        node = node.parent
    return False
