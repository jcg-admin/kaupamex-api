"""El punto de enganche de la cuenta propia, y por qué tiene que acumular.

Porta ``SELF_READABLE_FIELDS`` / ``SELF_WRITEABLE_FIELDS`` /
``_self_accessible_fields`` (``odoo19c: odoo/addons/base/models/res_users.py:
175-201``, LGPL-3). Cierra la tarea **#66** y el mayor bloque de la **#67**.

Lo que estaba mal, y no era teórico
------------------------------------

El docstring de ``base/models/res_users.py`` declaraba estos símbolos
bloqueados por el canal RPC crudo, y ``addons/hr`` **ya los implementaba** con
la nota *"sin base que extender"*. Dos referentes siempre presentes que se
contradecían.

El coste: sin base que extender, cada addon devuelve **su lista entera** en vez
de sumarla, así que dos addons que declaren la propiedad se pisan y gana el
último en instalarse. La fuente lo evita por construcción —su docstring dice
*"In order to add fields, please override this property on model extensions"*,
y una extensión suma con ``super()``—; aquí la propiedad se inyecta sobre la
clase, así que sumar es explícito.

Enterprise 19 lo extiende **13 veces en 7 addons**: es el símbolo de ``base``
que más extensiones recibe de todo el modelo (tarea #67).

El control que puede fallar
---------------------------

Haciendo que ``hr`` devuelva sólo su lista —el estado anterior— cae
``test_hr_adds_to_the_base_list_instead_of_replacing_it`` y sobreviven los
demás, que preguntan por la base y no por la suma.

*Métrica:* el contenido de las dos listas y de los dos conjuntos congelados.
*Ciega a:* si un consumidor las **usa** — hoy el control de campos lo ejerce el
serializer con su ``Meta.fields`` explícito y la capacidad (DEC-11). Estos
símbolos son el punto de enganche, no su aplicación.
"""
import pytest

from addons.base.models.res_users import ResUsers
from addons.hr.models.res_users import SELF_READABLE_FIELDS as hr_readable

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def test_the_base_list_is_not_empty(db):
    """Una lista vacía haría pasar por vacuidad todo lo de abajo."""
    assert ResUsers().SELF_READABLE_FIELDS


def test_writeable_is_not_derived_from_readable(db):
    """La fuente las declara por separado: legible no implica escribible."""
    user = ResUsers()
    assert set(user.SELF_WRITEABLE_FIELDS) < set(user.SELF_READABLE_FIELDS)


def test_login_is_readable_but_not_writeable(db):
    """El caso que hace la distinción concreta (``odoo19c: :180`` vs ``:192``)."""
    user = ResUsers()
    assert 'login' in user.SELF_READABLE_FIELDS
    assert 'login' not in user.SELF_WRITEABLE_FIELDS


def test_the_accessible_sets_are_frozen(db):
    """≙ ``_self_accessible_fields`` (``:195-201``): devuelve ``frozenset``."""
    readable, writeable = ResUsers._self_accessible_fields()
    assert isinstance(readable, frozenset)
    assert isinstance(writeable, frozenset)
    assert writeable < readable


def test_hr_adds_to_the_base_list_instead_of_replacing_it(db):
    """El defecto que cierra #66: la extensión SUMA, no reemplaza.

    Si ``hr`` devolviera sólo lo suyo, ningún campo de ``base`` sobreviviría a
    su instalación — y el siguiente addon que declarara la propiedad borraría
    a ``hr`` a su vez.
    """
    base = ResUsers().SELF_READABLE_FIELDS
    with_hr = hr_readable(ResUsers())
    assert set(base) < set(with_hr), 'hr reemplaza en vez de sumar'
    assert 'login' in with_hr
