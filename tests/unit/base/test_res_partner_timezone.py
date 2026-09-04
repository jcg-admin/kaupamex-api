"""``tz`` de ``res.partner`` es una Selection acotada, no un texto libre.

Cierra la tarea **#107**, que el propio ``_compute_tz_offset`` nombraba como
su sucesor: la fuente declara el campo como
``fields.Selection(_tzs, string='Timezone', ...)``
(``odoo19c: odoo/addons/base/models/res_partner.py:223``), y aqui era un
``fields.Char`` libre.

Se portan los DOS simbolos que la fuente declara, no solo el campo
(``porte-completo-no-parcial.md``):

- ``_tzs`` (``:40``) — la lista de pares, con su comentario verbatim:
  *"put POSIX 'Etc/\\*' entries at the end to avoid confusing users - see
  bug 1086728"*.
- ``_tz_get`` (``:41-42``) — el invocable que la devuelve. **No es adorno**:
  medido sobre ``odoo19c``, lo consumen **14 archivos / 30 referencias**
  (``lunch``, ``hr_holidays``, ``event``, ``resource``, ``mail``, ``website``,
  ``calendar``, mas ``base``), asi que es API compartida del arbol.

DIVERGENCIA DE STACK, declarada
--------------------------------

``pytz`` NO esta instalado (medido: ``ModuleNotFoundError``), asi que la
poblacion sale de ``zoneinfo.available_timezones()`` de la biblioteca
estandar. Medido en este contenedor: **498 zonas, 35 de ellas ``Etc/*``**.

*Metrica:* ``len(zoneinfo.available_timezones())``.
*Ciega a:* que las dos poblaciones coincidan zona por zona con
``pytz.all_timezones`` — no se puede comparar sin ``pytz`` instalado. Lo que
si se afirma es la FORMA: pares ``(tz, tz)`` con los ``Etc/*`` al final, que
es lo que el comentario de la fuente fija.

El control que puede fallar
---------------------------

``test_an_unknown_timezone_is_rejected`` es el unico caso que hoy no puede
pasar: con ``tz`` como ``Char`` libre, ``full_clean()`` acepta cualquier
cadena. Los otros cuatro miden la forma de ``_tzs``/``_tz_get``, que hoy ni
siquiera existen — asi que la suite entera esta roja antes del cambio, y eso
se cita en el hallazgo.

Lo que este porte NO cierra, y por que
--------------------------------------

``choices`` en Django es **validacion, no DDL** — el mismo hecho que
desbloqueo la tarea #118. PostgreSQL no recibe ningun ``CHECK``, asi que
``ResPartner.objects.create(tz='No/Existe')`` **sigue escribiendo la fila**:
solo ``full_clean()`` la rechaza. Por eso el respaldo a GMT de
``_compute_tz_offset`` **se queda**, y su caso en
``tests/integration/base/test_res_partner_labels.py`` tambien. Lo que se
corrige alli es el docstring, que anunciaba que #107 retiraria ese caso.
"""
import pytest
from django.core.exceptions import ValidationError

from addons.base.models.res_partner import ResPartner, _tz_get, _tzs

pytestmark = pytest.mark.django_db


class TestTimezoneVocabulary:
    """``_tzs`` y ``_tz_get`` — ≙ ``odoo19c: res_partner.py:40-42``."""

    def test_every_entry_is_a_pair_of_the_same_name(self):
        assert _tzs, 'la poblacion de zonas no puede estar vacia'
        assert all(isinstance(row, tuple) and len(row) == 2 and row[0] == row[1]
                   for row in _tzs)

    def test_posix_etc_entries_come_last(self):
        """El comentario de la fuente es el contrato, no una nota."""
        names = [name for name, _ in _tzs]
        etc = [i for i, name in enumerate(names) if name.startswith('Etc/')]
        assert etc, 'sin zonas Etc/* el caso no discrimina nada'
        assert etc == list(range(len(names) - len(etc), len(names)))

    def test_the_etc_block_is_itself_ordered(self):
        """El orden dentro del bloque ``Etc/*`` tiene que ser determinista.

        Es el segundo control que puede fallar, y no es cosmetico: con la
        clave literal de la fuente todas las ``Etc/*`` colapsan al mismo valor
        y su posicion la decide el recorrido del ``set`` de
        ``available_timezones()``, que cambia entre procesos. Medido: dos
        ``makemigrations`` seguidos daban bloques distintos, asi que
        ``makemigrations --check`` nunca quedaba limpio.
        """
        etc = [name for name, _ in _tzs if name.startswith('Etc/')]
        assert etc == sorted(etc)

    def test_the_local_machine_link_is_not_offered(self):
        """``localtime`` es el enlace de la maquina, no una zona.

        ``available_timezones()`` lo devuelve porque barre ``TZPATH`` y admite
        todo archivo con firma ``TZif``; su propio codigo retira ``posixrules``
        y NO este. ``pytz.all_timezones`` no lo tiene — es una lista curada.
        """
        assert 'localtime' not in {name for name, _ in _tzs}

    def test_the_rest_keeps_its_own_order(self):
        names = [name for name, _ in _tzs if not name.startswith('Etc/')]
        assert names == sorted(names)

    def test_tz_get_returns_the_same_population(self):
        assert _tz_get(None) == _tzs

    def test_the_field_declares_that_vocabulary(self):
        field = ResPartner._meta.get_field('tz')
        assert [name for name, _ in field.choices] == [name for name, _ in _tzs]


class TestTimezoneValidation:
    """La Selection acota lo que ``full_clean()`` admite."""

    def test_a_known_timezone_passes(self, db):
        who = ResPartner(name='Ana', tz='America/Mexico_City', is_company=False)
        who.full_clean(exclude=['company'])

    def test_an_unknown_timezone_is_rejected(self, db):
        """El control: hoy pasa porque el campo es un ``Char`` libre."""
        who = ResPartner(name='Ana', tz='No/Existe', is_company=False)
        with pytest.raises(ValidationError) as failure:
            who.full_clean(exclude=['company'])
        assert 'tz' in failure.value.error_dict

    def test_empty_stays_valid(self, db):
        """La fuente admite el campo sin fijar: su ``default`` puede ser None."""
        who = ResPartner(name='Ana', tz='', is_company=False)
        who.full_clean(exclude=['company'])
