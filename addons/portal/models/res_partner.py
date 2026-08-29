"""Reglas de edición del partner por un usuario de portal / público.

Adaptación fiel de Odoo ``portal/models/res_partner.py`` (LGPL-3, 55 loc,
leído completo). La referencia extiende ``res.partner`` con ``_inherit``.

**Dos mecanismos, y la frontera entre ellos es si otro addon los encadena.**
Hasta este pase los siete símbolos eran funciones de módulo sobre el partner
(mismo criterio que ``authz_ldap.res_users``). Dos de ellos dejan de serlo:

- ``_can_edit_country`` y ``can_edit_vat`` son **métodos** de ``ResPartner``,
  colgados con ``extend_model`` desde ``PortalConfig.ready()``. La razón es
  que ``sale`` los **encadena** — su fuente escribe
  ``super()._can_edit_country()`` (``odoo19c: sale/models/res_partner.py:67``)
  — y una función de módulo no admite ``super()``. Como método, el eslabón de
  ``sale`` recibe el de ``portal`` en la mano (``overrides=`` de
  ``extend_model``) y la cadena se recorre entera desde el consumidor.
- Los cinco restantes siguen siendo funciones de módulo: nadie los encadena.

  * ``_get_frontend_writable_fields`` → ``frontend_writable_fields()``: el
    allowlist de campos que un usuario de portal/público puede cambiar en su
    contacto (nunca campo libre — ver ``backend-drf/filtering``).
  * ``_can_be_edited_by_current_customer`` → ``can_be_edited_by(partner,
    user)``: el partner es editable si es el del usuario o un hijo de su
    entidad comercial con tipo dirección.
  * ``_get_current_partner`` → ``current_partner(user)``: el partner del
    usuario, o vacío si es público (usa ``ResUsers._is_public()``, el eje real
    portado en H-API-234).
  * ``_get_delivery_address_domain`` → NO portado: arma un ``Domain`` de Odoo
    para el selector de direcciones de envío del checkout QWeb; el filtrado de
    direcciones del SPA lo resuelve su propio endpoint.
  * ``_is_child_of`` es ayudante propio, no de la fuente: materializa el
    operador ``child_of`` sobre un candidato único.

El guion bajo se porta verbatim
===============================

``_can_edit_country`` lo declara privado la fuente y ``can_edit_vat`` público,
en el mismo archivo y a cuatro líneas de distancia. La distinción está escrita
a mano y se conserva: quitar el guion bajo no renombra, **promueve el símbolo a
API pública** (``porte-completo-no-parcial.md``, H-API-581). Hasta este pase la
función de módulo se llamaba ``can_edit_country``; sus dos consumidores
(``portal/controllers/main.py``) pasan a invocar el método.

La entidad comercial la resuelve ``ResPartner.commercial_partner``
=================================================================

Este archivo declaraba un ``_commercial_partner`` propio que subía por la
cadena de padres hasta el que no tuviera ``parent_id``. **No es el corte de la
fuente**: ``commercial_partner_id`` corta en ``is_company or not parent_id``
(``src/addons/base/models/res_partner.py:1422``), así que una empresa hija era
la entidad comercial allá y no aquí. Se retira el ayudante y se consulta la
``property`` ya portada, que es el símbolo con la semántica correcta.
"""
from orm.model_classes import extend_model


#: ≙ la cabecera que la fuente declara en su clase (la extensión aquí no es clase).
_inherit = 'res.partner'


def frontend_writable_fields():
    """≙ ``_get_frontend_writable_fields`` (res_partner.py:10-19)."""
    return {
        'name', 'phone', 'email', 'street', 'street2', 'city', 'state_id',
        'country_id', 'zip', 'zipcode', 'vat', 'company_name',
    }


def _can_edit_country(self):
    """≙ ``_can_edit_country`` (res_partner.py:21-23).

    El eslabón base de la cadena: ``portal`` no restringe el país. Quien sí
    lo hace es ``sale``, que encadena sobre este resultado.

    El ``ensure_one()`` de la fuente no se porta: guarda contra un recordset
    de N filas, y una instancia de Django es siempre una.
    """
    return True


def can_edit_vat(self):
    """≙ ``can_edit_vat`` (res_partner.py:25-30).

    *"``vat`` is a commercial field, synced between the parent (commercial
    entity) and the children. Only the commercial entity should be able to
    edit it (as in backend)."* — sólo el partner sin padre lo edita.
    """
    return self.parent_id is None


def current_partner(user):
    """≙ ``_get_current_partner`` (res_partner.py:44-49): el partner del
    usuario, o ``None`` si es público."""
    if user._is_public():
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
    return (
        partner.type in ('invoice', 'delivery', 'other')
        and _is_child_of(partner, current.commercial_partner)
    )


def _is_child_of(partner, ancestor):
    """True si ``partner`` es ``ancestor`` o un descendiente suyo
    (≙ el operador ``child_of`` de Odoo sobre la jerarquía de partners)."""
    node = partner
    while node is not None:
        if node.pk == ancestor.pk:
            return True
        node = node.parent
    return False


def apply_portal_partner_extensions():
    """Cuelga las dos guardas de edición. La llama ``PortalConfig.ready()``.

    Van por ``metodos=`` y no por ``overrides=`` porque son el **eslabón
    base**: no hay implementación previa que recibir. ``chain_method`` las
    instala tal cual cuando no encuentra una anterior.
    """
    extend_model(
        _inherit,
        metodos={
            '_can_edit_country': _can_edit_country,
            'can_edit_vat': can_edit_vat,
        },
    )
