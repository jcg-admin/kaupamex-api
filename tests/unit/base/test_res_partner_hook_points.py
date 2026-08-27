"""Los puntos de enganche del contacto (tarea #78).

Porta ``_address_fields``, ``_formatting_address_fields``,
``_commercial_fields`` y ``_synced_commercial_fields``
(``odoo19c: odoo/addons/base/models/res_partner.py:659-700``, LGPL-3).

Por qué existen aunque nadie los extienda todavía
--------------------------------------------------

El docstring de ``_commercial_fields`` en la fuente termina diciéndolo:
*"The list is meant to be extended by inheriting classes."* Enterprise 19 los
extiende **5 veces** (:ref:`h-api-819`), y cada addon suma a lo que devuelve el
``super()``. Sin base que extender, dos addons que los declararan se pisarían —
el defecto que ``SELF_READABLE_FIELDS`` tenía y que #66 cerró.

Son **cuatro** ganchos y no dos a propósito: la fuente separa sincronizar del
padre de formatear la dirección, y propagar hacia arriba de delegar hacia
abajo. Un addon puede querer más campos para formatear que para sincronizar, y
con un solo gancho tendría que elegir.

El control que puede fallar
---------------------------

Haciendo que ``_formatting_address_fields`` devuelva una lista literal en vez
de delegar en ``_address_fields``, cae
``test_formatting_delegates_to_the_synced_list`` y sobreviven los demás.

*Métrica:* el contenido de las cuatro listas, y que los campos que nombran
existan en el modelo.
*Ciega a:* si algo las **consume** — hoy la sincronización padre-hijo no está
cableada a estas listas. Son el punto de enganche, no su aplicación.
"""
import pytest

from addons.base.models.res_partner import ResPartner

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def test_every_address_field_exists_in_the_model(db):
    """El gancho no puede nombrar un campo que no está.

    La fuente los llama ``state_id``/``country_id``; aquí la convención los
    llama ``state``/``country``, y ésa es la única divergencia de la lista.
    """
    declarados = {f.name for f in ResPartner._meta.get_fields()}
    assert set(ResPartner._address_fields()) <= declarados


def test_formatting_delegates_to_the_synced_list(db):
    """≙ ``return self._address_fields()`` (``odoo19c: :667``)."""
    assert ResPartner._formatting_address_fields() == ResPartner._address_fields()


def test_synced_is_a_strict_subset_of_commercial(db):
    """Propagar hacia arriba es un subconjunto de delegar hacia abajo."""
    sincronizados = set(ResPartner._synced_commercial_fields())
    comerciales = set(ResPartner._commercial_fields())
    assert sincronizados <= comerciales


def test_commercial_names_only_fields_that_exist(db):
    """La fuente añade dos campos que este árbol no tiene; no se fabrican.

    ``company_registry`` sólo aparece en ``_rec_names_search`` sin campo detrás,
    e ``industry_id`` necesita ``res.partner.industry``, sin portar (tarea #48).
    """
    declarados = {f.name for f in ResPartner._meta.get_fields()}
    assert set(ResPartner._commercial_fields()) <= declarados
