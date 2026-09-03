"""El ``ilike`` insensible a acentos — la extension ``unaccent`` de PostgreSQL.

La fuente envuelve los dos lados de un ``ilike`` con ``registry.unaccent``
(``odoo19c: odoo/orm/fields.py:1326-1327``) y normaliza igual el predicado en
memoria con ``unaccent_python`` (``:1420-1423``). Aqui las dos vias comparaban
**con** el acento, y tres docstrings lo declaraban como bloqueo: *"la extension
no esta instalada"*.

Medido el 2026-09-03 contra ``pg_available_extensions``: ``unaccent`` estaba
**disponible** (version 1.1) y sin crear. No era un bloqueo — era un
``CREATE EXTENSION`` que nadie ejecutaba. El provisioner de ``db`` si lo
declara (``db: provisioners/postgresql/db_setup.sh:194-195``), pero pytest crea
sus bases desde las migraciones, no desde el provisioner: de ahi que faltara
justo donde se mide.

**El control que discrimina** es ``test_like_does_not_unaccent``: la fuente
envuelve **solo** cuando el operador termina en ``ilike``. Sin ese caso, envolver
las dos familias pasaria igual de verde y nadie lo notaria.
"""
import pytest
from django.db import connection

from addons.base.models.res_partner import ResPartner
from orm.domains import Domain
from orm.fields import UNACCENT_ENABLED
from orm.models import filtered_domain


def _names(rows):
    return sorted(r.name for r in rows)


class TestTheExtensionIsInstalled:
    """La extension vive en la base, puesta por migracion."""

    @pytest.mark.django_db
    def test_the_extension_is_created(self):
        with connection.cursor() as cr:
            cr.execute("SELECT 1 FROM pg_extension WHERE extname = 'unaccent'")
            assert cr.fetchone() is not None

    @pytest.mark.django_db
    def test_the_one_argument_function_exists(self):
        """Lo que la fuente pregunta no es la extension, es la funcion.

        ``modules.db.has_unaccent`` mira ``pg_proc``, no ``pg_extension``:
        cualquier funcion homonima de un argumento sirve.
        """
        with connection.cursor() as cr:
            cr.execute(
                "SELECT provolatile FROM pg_proc "
                "WHERE proname = 'unaccent' AND pronargs = 1")
            rows = cr.fetchall()
        assert rows, 'unaccent/1 no existe'

    def test_the_flag_is_on(self):
        """Las dos vias leen esta bandera; encenderla es una decision, no dos."""
        assert UNACCENT_ENABLED is True


class TestBothWaysIgnoreTheAccent:
    """El motor y el predicado en memoria deciden lo mismo."""

    @pytest.fixture
    def partners(self, db):
        created = [
            ResPartner.objects.create(name='Ácme'),
            ResPartner.objects.create(name='Acme Junior'),
            ResPartner.objects.create(name='Beta'),
        ]
        yield created
        for p in created:
            p.delete()

    @pytest.mark.django_db
    def test_the_engine_finds_the_accented_row(self, partners):
        found = ResPartner.objects.filter(
            pk__in=[p.pk for p in partners]).filter(
                Domain([('name', 'ilike', 'acme')])._to_q(ResPartner))
        assert _names(found) == ['Acme Junior', 'Ácme']

    @pytest.mark.django_db
    def test_the_in_memory_predicate_finds_it_too(self, partners):
        assert _names(filtered_domain(partners, [('name', 'ilike', 'acme')])) == [
            'Acme Junior', 'Ácme',
        ]

    @pytest.mark.django_db
    def test_the_two_ways_agree(self, partners):
        """La razon por la que la bandera existe: un solo veredicto."""
        domain = [('name', 'ilike', 'acme')]
        from_engine = ResPartner.objects.filter(
            pk__in=[p.pk for p in partners]).filter(Domain(domain)._to_q(ResPartner))
        assert _names(filtered_domain(partners, domain)) == _names(from_engine)

    @pytest.mark.django_db
    def test_it_works_in_the_other_direction_too(self, partners):
        """Buscar con acento encuentra la fila sin acento."""
        assert _names(filtered_domain(partners, [('name', 'ilike', 'ácme')])) == [
            'Acme Junior', 'Ácme',
        ]


class TestOnlyILikeUnaccents:
    """El control: la fuente envuelve solo la familia insensible a mayusculas."""

    @pytest.mark.django_db
    def test_like_does_not_unaccent(self, db):
        """``like`` es sensible a mayusculas Y a acentos, en las dos vias."""
        row = ResPartner.objects.create(name='Ácme')
        try:
            domain = [('name', 'like', 'Acme')]
            from_engine = ResPartner.objects.filter(pk=row.pk).filter(
                Domain(domain)._to_q(ResPartner))
            assert list(from_engine) == []
            assert list(filtered_domain([row], domain)) == []
        finally:
            row.delete()

    @pytest.mark.django_db
    def test_the_ilike_sql_names_the_function(self):
        """La consulta emitida lleva ``unaccent(`` en los dos lados."""
        query = str(ResPartner.objects.filter(
            Domain([('name', 'ilike', 'acme')])._to_q(ResPartner)).query)
        assert query.lower().count('unaccent(') >= 2
