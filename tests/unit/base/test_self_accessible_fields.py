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

El control que NO podía fallar, y por qué
------------------------------------------

Este archivo tenía un caso llamado
``test_hr_adds_to_the_base_list_instead_of_replacing_it`` que llamaba a la
**función** ``hr.SELF_READABLE_FIELDS(ResUsers())`` y comprobaba que sumara.
Sumaba. Y la property instalada sobre el modelo **no la contenía**: ``hr`` la
cableaba por ``extend_model(propiedades=…)``, que no pisa una existente, así
que la función nunca llegaba al modelo. Medido: los **32** campos de ``hr``
ausentes de ``ResUsers().SELF_READABLE_FIELDS``.

El verde no distinguía *"la extensión suma"* de *"la extensión no está
instalada"* — el sub-patrón D de ``metrica-decide-la-conclusion.md`` dentro del
control que #66 dejó puesto. Ver :ref:`h-api-834`.

Los casos preguntan ahora por la **property del modelo**, que es lo que un
consumidor lee. Qué los haría fallar: devolver ``propiedades=`` a
``apply_hr_res_users_extensions`` — caen los dos de acumulación y sobreviven
los que sólo miran la base.

*Métrica:* el contenido de las dos listas leídas desde el modelo, y de los dos
conjuntos congelados.
*Ciega a:* si un consumidor las **usa** — hoy el control de campos lo ejerce el
serializer con su ``Meta.fields`` explícito y la capacidad (DEC-11). Estos
símbolos son el punto de enganche, no su aplicación.
"""
import pytest

from addons.base.models.res_users import ResUsers
from addons.hr.models.res_users import (
    HR_READABLE_FIELDS, HR_WRITABLE_FIELDS,
    SELF_READABLE_FIELDS as hr_readable,
)

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


def test_the_hr_fields_reach_the_installed_property(db):
    """CONTROL — se pregunta al MODELO, no a la función de ``hr``.

    Es la corrección de :ref:`h-api-834`: la versión anterior llamaba a la
    función y por eso no podía ver que nadie la instalaba.
    """
    fields = set(ResUsers().SELF_READABLE_FIELDS)
    from_hr = set(HR_READABLE_FIELDS) | set(HR_WRITABLE_FIELDS)
    assert from_hr <= fields, sorted(from_hr - fields)


def test_the_three_layers_accumulate(db):
    """``base`` + ``hr`` + ``hr_homeworking``, las tres en la misma lista.

    Con dos capas no basta para separar *"suma"* de *"gana la última"*: la
    tercera es la que lo prueba, porque ``hr_homeworking`` se instala después
    de ``hr`` y sus días conviven con los campos de ``hr``.
    """
    fields = set(ResUsers().SELF_READABLE_FIELDS)
    assert 'login' in fields, 'se perdió la capa de base'
    assert 'job_title' in fields, 'se perdió la capa de hr'
    assert 'monday_location' in fields, 'se perdió la capa de hr_homeworking'


def test_the_hr_function_sums_onto_what_it_receives(db):
    """La función en sí: recibe el ``super()`` y lo conserva.

    Separado del caso de arriba a propósito — aquél mide que esté
    **instalada**, éste que su cuerpo **sume**. Juntos distinguen los dos modos
    de fallo que el caso original confundía en uno.
    """
    with_hr = hr_readable(ResUsers(), ['centinela'])
    assert 'centinela' in with_hr, 'hr reemplaza en vez de sumar'
    assert 'job_title' in with_hr
